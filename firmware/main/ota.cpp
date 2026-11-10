#include "ota.h"

#include <atomic>
#include <cstdio>
#include <cstring>
#include <string>

#include "core/config.h"
#include "esp_app_desc.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

static const char* TAG = "ota";

namespace {

SemaphoreHandle_t Mu() {
  static SemaphoreHandle_t m = xSemaphoreCreateMutex();
  return m;
}
std::atomic<bool> g_busy{false};
std::atomic<int> g_progress{-1};  // percent, -1 when not downloading
std::string g_state = "idle";     // idle, checking, downloading, rebooting, error
std::string g_latest;             // version from index.json, once checked
std::string g_message;

void Set(const char* state, const std::string& msg) {
  xSemaphoreTake(Mu(), portMAX_DELAY);
  g_state = state;
  g_message = msg;
  xSemaphoreGive(Mu());
  ESP_LOGI(TAG, "%s: %s", state, msg.c_str());
}

const char* Version() { return esp_app_get_description()->version; }

void RebootSoon() {
  Set("rebooting", "update installed: restarting");
  vTaskDelay(pdMS_TO_TICKS(1500));
  esp_restart();
}

// GET a small HTTPS resource into `out` (max 8 KB).
esp_err_t Fetch(const std::string& url, std::string& out) {
  esp_http_client_config_t c = {};
  c.url = url.c_str();
  c.crt_bundle_attach = esp_crt_bundle_attach;
  c.timeout_ms = 15000;
  esp_http_client_handle_t h = esp_http_client_init(&c);
  if (!h) return ESP_FAIL;
  esp_err_t err = esp_http_client_open(h, 0);
  if (err == ESP_OK) {
    esp_http_client_fetch_headers(h);
    const int status = esp_http_client_get_status_code(h);
    char buf[512];
    int n;
    while ((n = esp_http_client_read(h, buf, sizeof(buf))) > 0 && out.size() < 8192) out.append(buf, n);
    if (status != 200) err = ESP_FAIL;
  }
  esp_http_client_cleanup(h);
  return err;
}

bool CheckLatest() {
  std::string body;
  if (Fetch(std::string(ota::kSiteBase) + "/index.json", body) != ESP_OK) {
    Set("error", "couldn't reach GitHub: join the controller to a WiFi network with internet (Settings, WiFi)");
    return false;
  }
  cJSON* j = cJSON_Parse(body.c_str());
  const cJSON* v = j ? cJSON_GetObjectItemCaseSensitive(j, "version") : nullptr;
  if (!cJSON_IsString(v)) {
    cJSON_Delete(j);
    Set("error", "unexpected index.json from the update site");
    return false;
  }
  xSemaphoreTake(Mu(), portMAX_DELAY);
  g_latest = v->valuestring;
  xSemaphoreGive(Mu());
  const bool same = g_latest == Version();
  cJSON_Delete(j);
  Set("idle", same ? "up to date" : "update available: " + g_latest);
  return true;
}

void CheckTask(void*) {
  CheckLatest();
  g_busy = false;
  vTaskDelete(nullptr);
}

void InstallTask(void*) {
  if (!CheckLatest()) {
    g_busy = false;
    vTaskDelete(nullptr);
  }
  const std::string url = std::string(ota::kSiteBase) + "/" + scorbot::kVariantId + "/scorbot_controller.bin";
  Set("downloading", "downloading " + g_latest + " (" + scorbot::kVariantId + ")");
  esp_http_client_config_t hc = {};
  hc.url = url.c_str();
  hc.crt_bundle_attach = esp_crt_bundle_attach;
  hc.timeout_ms = 20000;
  hc.keep_alive_enable = true;
  esp_https_ota_config_t oc = {};
  oc.http_config = &hc;
  esp_https_ota_handle_t h = nullptr;
  esp_err_t err = esp_https_ota_begin(&oc, &h);
  if (err == ESP_OK) {
    g_progress = 0;
    while ((err = esp_https_ota_perform(h)) == ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
      const int total = esp_https_ota_get_image_size(h);
      if (total > 0) g_progress = static_cast<int>(100LL * esp_https_ota_get_image_len_read(h) / total);
    }
    if (err == ESP_OK && !esp_https_ota_is_complete_data_received(h)) err = ESP_FAIL;
    if (err == ESP_OK) {
      err = esp_https_ota_finish(h);  // verifies the image and switches the boot slot
    } else {
      esp_https_ota_abort(h);
    }
  }
  g_progress = -1;
  if (err == ESP_OK) RebootSoon();
  Set("error", std::string("update failed: ") + esp_err_to_name(err));
  g_busy = false;
  vTaskDelete(nullptr);
}

bool Claim(const char* what) {
  bool expected = false;
  if (!g_busy.compare_exchange_strong(expected, true)) return false;
  Set(what, "");
  return true;
}

}  // namespace

namespace ota {

void StartCheck() {
  if (Claim("checking")) xTaskCreate(CheckTask, "ota_check", 8192, nullptr, 3, nullptr);
}

void StartInstall() {
  if (Claim("downloading")) xTaskCreate(InstallTask, "ota", 8192, nullptr, 3, nullptr);
}

esp_err_t ReceiveUpload(httpd_req_t* req, const char** error) {
  if (!Claim("downloading")) {
    *error = "an update is already running";
    return ESP_FAIL;
  }
  const esp_partition_t* slot = esp_ota_get_next_update_partition(nullptr);
  esp_ota_handle_t h = 0;
  esp_err_t err = slot ? esp_ota_begin(slot, OTA_WITH_SEQUENTIAL_WRITES, &h) : ESP_ERR_NOT_FOUND;
  if (err != ESP_OK) {
    *error = "no spare app slot (install once over USB to get the OTA layout)";
    g_busy = false;
    Set("error", *error);
    return err;
  }
  Set("downloading", "receiving uploaded file");
  const size_t total = req->content_len;
  size_t got = 0;
  char buf[2048];
  while (got < total) {
    const int n = httpd_req_recv(req, buf, sizeof(buf));
    if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
    if (n <= 0) {
      err = ESP_FAIL;
      break;
    }
    if ((err = esp_ota_write(h, buf, n)) != ESP_OK) break;
    got += n;
    g_progress = static_cast<int>(100LL * got / total);
  }
  g_progress = -1;
  if (err == ESP_OK) err = esp_ota_end(h);  // checks the image (magic, checksum)
  else esp_ota_abort(h);
  if (err == ESP_OK) err = esp_ota_set_boot_partition(slot);
  if (err != ESP_OK) {
    *error = err == ESP_ERR_OTA_VALIDATE_FAILED ? "that file isn't a valid controller firmware image" : "upload failed";
    Set("error", *error);
    g_busy = false;
    return err;
  }
  xTaskCreate([](void*) { RebootSoon(); }, "reboot", 3072, nullptr, 1, nullptr);
  return ESP_OK;
}

cJSON* Status() {
  cJSON* j = cJSON_CreateObject();
  cJSON_AddStringToObject(j, "version", Version());
  cJSON_AddStringToObject(j, "variant", scorbot::kVariantId);
  cJSON_AddStringToObject(j, "driver", scorbot::kDriverName);
  const esp_partition_t* run = esp_ota_get_running_partition();
  cJSON_AddStringToObject(j, "slot", run ? run->label : "?");
  cJSON_AddBoolToObject(j, "ota_layout", esp_ota_get_next_update_partition(nullptr) != nullptr);
  cJSON_AddBoolToObject(j, "busy", g_busy.load());
  cJSON_AddNumberToObject(j, "progress", g_progress.load());
  xSemaphoreTake(Mu(), portMAX_DELAY);
  cJSON_AddStringToObject(j, "state", g_state.c_str());
  cJSON_AddStringToObject(j, "latest", g_latest.c_str());
  cJSON_AddStringToObject(j, "message", g_message.c_str());
  xSemaphoreGive(Mu());
  return j;
}

void MarkGood() {
  esp_ota_img_states_t st;
  const esp_partition_t* run = esp_ota_get_running_partition();
  if (run && esp_ota_get_state_partition(run, &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY) {
    esp_ota_mark_app_valid_cancel_rollback();
    ESP_LOGI(TAG, "new firmware %s confirmed", Version());
  }
}

}  // namespace ota

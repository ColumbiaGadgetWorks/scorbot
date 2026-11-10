// Firmware updates over WiFi: from the project's GitHub Pages site (the same
// builds the web installer uses), or from a .bin file uploaded by the browser.
#pragma once
#include "cJSON.h"
#include "esp_err.h"
#include "esp_http_server.h"

namespace ota {

// Where CI publishes the firmware: <base>/index.json and <base>/<variant>/scorbot_controller.bin
constexpr const char* kSiteBase = "https://columbiagadgetworks.github.io/scorbot/firmware";

// Starts a background check of index.json (returns at once; poll Status()).
void StartCheck();
// Starts a background download + install of this variant's latest build, then reboots.
void StartInstall();
// Streams an uploaded app image (raw .bin body) into the spare slot, then reboots.
esp_err_t ReceiveUpload(httpd_req_t* req, const char** error);
// {"version","variant","state","progress","latest","message","busy"}. Caller frees.
cJSON* Status();
// After a successful boot: keep this image (cancels the automatic rollback).
void MarkGood();

}  // namespace ota

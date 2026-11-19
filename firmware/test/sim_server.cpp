// Runs the real robot core + JSON API against SimArm in real time.
// stdin:  one JSON command per line ({"cmd":...,"id":N}); "__get_config" /
//         "__set_config" read and write the config like /api/config.
// stdout: every 50 ms "S <state json>" (for /api/state) and "L <hex wire::Live>"
//         (the binary /ws frame); "I <info json>" when it changes; "R <reply json>"
//         per command.
// Used by sim_bridge.py to serve the web UI without hardware.
#include <poll.h>
#include <unistd.h>

#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <thread>

#include "../main/api.h"
#include "../main/settings.h"
#include "sim_hal.h"

using namespace scorbot;

int main() {
  SimArm sim;
  RobotConfig cfg = DefaultConfig();
  Robot robot(sim, cfg);
  HwInfo hw;
  hw.expander = true;
  hw.adc[0] = hw.adc[1] = true;
  hw.net_mode = "sim";
  std::snprintf(hw.ip, sizeof(hw.ip), "127.0.0.1");
  std::snprintf(hw.ssid, sizeof(hw.ssid), "simulator");
  setvbuf(stdout, nullptr, _IOLBF, 0);

  std::string line, last_info;
  auto next = std::chrono::steady_clock::now();
  for (uint32_t frame = 0;; ++frame) {
    for (int i = 0; i < 50; ++i) {  // 50 ms of 1 kHz control
      robot.update(0.001f);
      sim.step(0.001f);
    }
    // commands
    pollfd p = {0, POLLIN, 0};
    while (poll(&p, 1, 0) > 0 && (p.revents & POLLIN)) {
      char buf[8192];
      if (!fgets(buf, sizeof(buf), stdin)) return 0;
      cJSON* msg = cJSON_Parse(buf);
      if (!msg) continue;
      cJSON* reply = cJSON_CreateObject();
      const cJSON* c = cJSON_GetObjectItemCaseSensitive(msg, "cmd");
      const char* cmd = cJSON_IsString(c) ? c->valuestring : "";
      if (!std::strcmp(cmd, "__get_config")) {
        cJSON_AddBoolToObject(reply, "ok", true);
        cJSON_AddItemToObject(reply, "config", settings::RobotToJson(cfg));
      } else if (!std::strcmp(cmd, "__set_config")) {
        settings::RobotFromJson(cJSON_GetObjectItemCaseSensitive(msg, "config"), cfg);
        cJSON_AddBoolToObject(reply, "ok", true);
        cJSON_AddItemToObject(reply, "config", settings::RobotToJson(cfg));
      } else if (!std::strcmp(cmd, "__sim")) {  // test hooks: E-stop, jams
        const cJSON* vm = cJSON_GetObjectItemCaseSensitive(msg, "vm");
        if (cJSON_IsBool(vm)) sim.vm = cJSON_IsTrue(vm);
        cJSON_AddBoolToObject(reply, "ok", true);
      } else {
        bool changed;
        api::Command(robot, cfg, msg, reply, &changed);
      }
      const cJSON* id = cJSON_GetObjectItemCaseSensitive(msg, "id");
      if (cJSON_IsNumber(id)) cJSON_AddNumberToObject(reply, "id", id->valuedouble);
      char* s = cJSON_PrintUnformatted(reply);
      std::printf("R %s\n", s);
      cJSON_free(s);
      cJSON_Delete(reply);
      cJSON_Delete(msg);
    }
    hw.uptime_s = frame / 20;
    cJSON* st = api::State(robot, cfg, hw);
    char* s = cJSON_PrintUnformatted(st);
    std::printf("S %s\n", s);
    cJSON_free(s);
    cJSON_Delete(st);
    wire::Live live;
    api::FillLive(robot, cfg, hw, &live);
    std::string hex;
    hex.reserve(2 * sizeof(live));
    for (size_t i = 0; i < sizeof(live); ++i) {
      static const char* d = "0123456789abcdef";
      const uint8_t b = reinterpret_cast<const uint8_t*>(&live)[i];
      hex += d[b >> 4];
      hex += d[b & 15];
    }
    std::printf("L %s\n", hex.c_str());
    InfoSnapshot snap;
    api::Snapshot(robot, &snap);
    cJSON* info = api::Info(snap, hw);
    char* is = cJSON_PrintUnformatted(info);
    if (last_info != is) {
      last_info = is;
      std::printf("I %s\n", is);
    }
    cJSON_free(is);
    cJSON_Delete(info);
    next += std::chrono::milliseconds(50);
    std::this_thread::sleep_until(next);
  }
}

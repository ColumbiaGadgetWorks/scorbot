// JSON command dispatcher and state snapshots, shared by REST and WebSocket.
// Portable (cJSON + core only) so it is unit-tested on the host.
#pragma once
#include <cstddef>
#include <cstdint>

#include "cJSON.h"
#include "core/robot.h"

struct HwInfo {
  bool expander = false, adc[2] = {false, false};
  const char* net_mode = "";  // "sta", "ap", "ap+sta"
  char ip[16] = "";
  char ssid[33] = "";
  int rssi = 0;
  uint32_t uptime_s = 0;
  const char* reset = "";  // why the ESP32 last restarted, e.g. "brownout"
};

namespace wire {
// Live state, pushed on /ws as one binary frame at 20 Hz (284 bytes, against
// ~2.5 KB of JSON). Fixed little-endian layout: the ESP32 and every browser
// platform are little-endian, and each array starts on a 4-byte boundary, so
// the page reads it in place through typed-array views, with no parsing and no
// copies. Changing the layout: bump kVersion and update decodeLive() in
// web/index.html (and LIVE_FMT in test/check_wire.py).
constexpr uint16_t kMagic = 0x5342;  // reads as 0x5342 only in little-endian
constexpr uint8_t kVersion = 1;

struct Live {
  uint16_t magic;       // kMagic
  uint8_t version;      // kVersion
  uint8_t mode;         // scorbot::Mode
  uint8_t flags;        // bit 0 enabled, bit 1 vm_ok, bit 2 driver fault
  int8_t busy;          // joint/motor of the running job, -1 = none
  uint8_t homed;        // bit j = joint j homed
  uint8_t calibrated;   // bit j = joint j counts/unit measured
  uint8_t sw;           // bit s = home switch s pressed
  uint8_t sw_on;        // bit s = seen pressed since the switch test reset
  uint8_t sw_off;       // bit s = seen released
  int8_t rssi;          // WiFi dBm, 0 = not connected
  float vm;             // motor supply volts, NaN = no ADC
  float pos[scorbot::kJoints];  // degrees (gripper mm)
  float tgt[scorbot::kJoints];
  float duty[scorbot::kMotors];
  float cur[scorbot::kMotors];  // amps, NaN = no ADC
  int32_t counts[scorbot::kMotors];
  int32_t emin[scorbot::kMotors];  // encoder test: range seen
  int32_t emax[scorbot::kMotors];
  uint32_t uptime_s;
  char fault[64];       // NUL-terminated
  char phase[32];
};
static_assert(sizeof(float) == 4, "wire floats are IEEE-754 single");
static_assert(offsetof(Live, vm) == 12 && offsetof(Live, pos) == 16 && offsetof(Live, tgt) == 40 &&
                  offsetof(Live, duty) == 64 && offsetof(Live, cur) == 88 && offsetof(Live, counts) == 112 &&
                  offsetof(Live, emin) == 136 && offsetof(Live, emax) == 160 && offsetof(Live, uptime_s) == 184 &&
                  offsetof(Live, fault) == 188 && offsetof(Live, phase) == 252 && sizeof(Live) == 284,
              "wire::Live layout is shared with web/index.html: keep them in step");
}  // namespace wire

// The slow-changing part of the state (test and calibration results), copied
// under the robot lock so its JSON can be built after releasing it.
struct InfoSnapshot {
  scorbot::MotorTestResult mtest[scorbot::kMotors];
  scorbot::CalibResult cal[scorbot::kJoints];
};

namespace api {
// Fills the binary live frame. Cheap (a field-by-field copy): call it with the
// robot lock held.
void FillLive(const scorbot::Robot& robot, const scorbot::RobotConfig& cfg, const HwInfo& hw, wire::Live* out);
void Snapshot(const scorbot::Robot& robot, InfoSnapshot* out);
// {"t":"info", mtest, cal, hw}: sent on /ws as text, only when it changes.
cJSON* Info(const InfoSnapshot& snap, const HwInfo& hw);
// Builds the full state message ({"t":"state", ...}). Caller frees.
cJSON* State(const scorbot::Robot& robot, const scorbot::RobotConfig& cfg, const HwInfo& hw);
// Runs one command message ({"cmd":"...", ...}). Fills `reply` with
// {"ok":bool,"error":"..."}; sets *config_changed when the config should be saved.
void Command(scorbot::Robot& robot, scorbot::RobotConfig& cfg, const cJSON* msg, cJSON* reply, bool* config_changed);
}  // namespace api

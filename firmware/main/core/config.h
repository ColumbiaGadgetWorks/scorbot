// Robot configuration: everything that calibration or the web UI can change.
// Portable C++ (no ESP-IDF headers) so the core can be unit-tested on a PC.
#pragma once
#include <cstdint>
#if __has_include("sdkconfig.h")
#include "sdkconfig.h"
#endif

namespace scorbot {

constexpr int kJoints = 6;   // base, shoulder, elbow, wrist pitch, wrist roll, gripper
constexpr int kMotors = 6;   // motor 4/5 drive pitch+roll through the differential wrist
constexpr int kSwitches = 5; // home microswitches on joints 0..4 (gripper has none)

// Motor driver carriers: all six the same, either DRV8874 (Pololu #4035 or
// the clone in hardware/drv8874-carrier, the default) or DRV8876 (Pololu
// #4036; menuconfig "Scorbot" or -DSCORBOT_DRV8876). Same pins; the current
// mirror differs. CS has 2.49k, and the driver chops at VREF / (gain x 2.49k)
// with VREF pulled to SLEEP (3.3 V).
#if defined(SCORBOT_DRV8876) || defined(CONFIG_SCORBOT_DRV8876)
constexpr const char* kDriverName = "DRV8876";
constexpr float kCsVoltsPerAmp = 2.49f;        // 1000 uA/A x 2.49k
constexpr float kDriverCurrentLimitA = 1.33f;  // carrier rated 1.3 A continuous
constexpr float kDefaultTripA = 1.2f;
#else
constexpr const char* kDriverName = "DRV8874";
constexpr float kCsVoltsPerAmp = 1.12f;        // 450 uA/A x 2.49k
constexpr float kDriverCurrentLimitA = 2.94f;  // carrier rated 2.1 A continuous
constexpr float kDefaultTripA = 2.5f;
#endif

enum Joint : int { kBase = 0, kShoulder, kElbow, kPitch, kRoll, kGripper };

struct MotorConfig {
  int8_t motor_dir = 1;     // flips PWM sign so +duty gives +counts (set by the motor test)
  int8_t enc_dir = 1;       // flips encoder sign (sets which way is "positive")
  float kp = 0.004f;        // duty per count of error
  float ki = 0.0008f;       // duty per count*second
  float kd = 0.00002f;      // duty per count/second
  float i_zone = 300.f;     // integrate only when |error| < this many counts
  float min_duty = 0.30f;   // static-friction compensation (reference build needed ~0.8)
  float max_duty = 1.0f;
};

struct JointConfig {
  char name[12] = "";
  bool has_switch = true;
  int8_t home_dir = -1;     // direction to seek the home switch from the far side
  float spec_min = -180.f;  // degrees (mm for the gripper) from the manual
  float spec_max = 180.f;
  bool continuous = false;  // wrist roll: no hard stops
  float counts_per_unit = 100.f;  // encoder counts per degree (per mm for gripper)
  bool cpu_calibrated = false;    // false = still the built-in estimate
  float home_pos = 0.f;     // joint angle at the home edge, degrees (mm)
  float soft_min = -180.f;  // soft limits, degrees (mm); set by calibration
  float soft_max = 180.f;
  float vmax = 45.f;        // degrees/s (mm/s)
  float amax = 180.f;       // degrees/s^2
  float home_speed = 10.f;  // seek speed, degrees/s
  float follow_err = 8.f;   // following-error fault limit, degrees (mm)
  uint16_t stall_ms = 150;  // stall window (reference build: 400 ms on shoulder/pitch)
};

struct RobotConfig {
  MotorConfig motor[kMotors];
  JointConfig joint[kJoints];
  float roll_ratio = 1.0f;          // roll counts / pitch counts for the same motor travel
  float calib_duty = 0.6f;          // duty cap while driving into hard stops
  float test_duty = 0.7f;           // duty for the open-loop motor test
  uint16_t test_ms = 300;           // pulse length per direction for the motor test
  float current_limit_a = kDefaultTripA;  // software over-current trip, below kDriverCurrentLimitA
  uint8_t home_order[kJoints] = {kShoulder, kElbow, kPitch, kRoll, kGripper, kBase};
  float gripper_open_mm = 40.f;     // opening after homing the gripper
  uint16_t jog_timeout_ms = 300;    // jog stops if no heartbeat
};

// Defaults from the SCORBOT-ER 4u manual (joint ranges) plus estimates for
// counts-per-degree that the calibration routine replaces.
RobotConfig DefaultConfig();

}  // namespace scorbot

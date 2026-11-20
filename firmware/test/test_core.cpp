// Host tests for the portable robot core, run against SimArm.
// Build and run: make -C firmware/test
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <functional>

#include "sim_hal.h"

using namespace scorbot;

static int g_fail = 0, g_pass = 0;
#define CHECK(cond, ...)                                  \
  do {                                                    \
    if (cond) {                                           \
      ++g_pass;                                           \
    } else {                                              \
      ++g_fail;                                           \
      std::printf("  FAIL %s:%d: %s  ", __FILE__, __LINE__, #cond); \
      std::printf(__VA_ARGS__);                           \
      std::printf("\n");                                  \
    }                                                     \
  } while (0)

struct Rig {
  SimArm sim;
  RobotConfig cfg = DefaultConfig();
  Robot robot{sim, cfg};
  // Run for up to `seconds`, stopping early when `done` returns true.
  bool run(float seconds, std::function<bool()> done = nullptr) {
    const float dt = 0.001f;
    for (int i = 0; i < static_cast<int>(seconds / dt); ++i) {
      robot.update(dt);
      sim.step(dt);
      if (done && done()) return true;
    }
    return !done;
  }
  bool idle() { return robot.status().mode == Mode::kIdle; }
};

static void TestEnableAndMove() {
  std::puts("move: enable and move base 30 deg");
  Rig r;
  r.run(0.05f);
  CHECK(r.robot.enable(), "%s", r.robot.lastError());
  float tgt[kJoints] = {};
  bool use[kJoints] = {};
  const float start = r.robot.status().pos[kBase];
  tgt[kBase] = start + 30.f;
  use[kBase] = true;
  CHECK(r.robot.moveTo(tgt, use, 0.5f), "%s", r.robot.lastError());
  // what the move reply tells the web UI to animate
  CHECK(std::fabs(r.robot.moveTarget(kBase) - tgt[kBase]) < 0.05f, "planned target %.2f", r.robot.moveTarget(kBase));
  const float planned_T = r.robot.moveTime();
  CHECK(planned_T > 0.1f && planned_T < 10.f, "planned time %.2f s", planned_T);
  CHECK(r.run(10.f, [&] { return r.idle(); }), "move did not finish");
  r.run(0.5f);
  float err = r.robot.status().pos[kBase] - tgt[kBase];
  CHECK(std::fabs(err) < 0.5f, "base error %.2f deg", err);
  CHECK(r.robot.status().mode == Mode::kIdle, "mode %s", ModeName(r.robot.status().mode));
}

static void TestHomeAll() {
  std::puts("home: all joints in configured order");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  CHECK(r.robot.home(-1), "%s", r.robot.lastError());
  bool ok = r.run(240.f, [&] { return r.robot.status().mode != Mode::kHoming; });
  CHECK(ok, "homing timed out in phase '%s' joint %d", r.robot.status().phase, r.robot.status().busy_joint);
  CHECK(r.robot.status().mode == Mode::kIdle, "mode %s fault '%s'", ModeName(r.robot.status().mode), r.robot.status().fault);
  for (int j = 0; j < kJoints; ++j) CHECK(r.robot.status().homed[j], "joint %d not homed", j);
  // Each switch joint should now sit at the switch edge it homed to.
  for (int j = 0; j < kSwitches; ++j) {
    float d = std::fabs(std::remainder(r.sim.jointDeg(j) - r.sim.switch_at[j], j == kRoll ? 360.f : 1e9f));
    CHECK(d < r.sim.switch_width, "joint %d ended %.2f deg from its switch", j, d);
  }
  CHECK(std::fabs(r.robot.status().pos[kGripper] - r.cfg.gripper_open_mm) < 1.0f, "gripper at %.1f mm",
        r.robot.status().pos[kGripper]);
}

static void TestHomeFromOnSwitch() {
  std::puts("home: starting with the switch already pressed");
  Rig r;
  r.sim = SimArm();
  r.sim.start_deg[kElbow] = r.sim.switch_at[kElbow];
  r.sim = SimArm();
  float jc[kJoints];
  SimArm::ToJoints(r.sim.mcount, jc);
  jc[kElbow] = r.sim.switch_at[kElbow] * r.sim.true_cpu[kElbow];
  SimArm::ToMotors(jc, r.sim.mcount);
  r.run(0.05f);
  CHECK(r.robot.status().sw[kElbow], "switch should start pressed");
  r.robot.enable();
  r.robot.home(kElbow);
  CHECK(r.run(60.f, [&] { return r.robot.status().mode != Mode::kHoming; }), "timeout");
  CHECK(r.robot.status().homed[kElbow], "elbow not homed, fault '%s'", r.robot.status().fault);
}

// Like the real ER-4u shoulder: the switch sits against a hard stop, so it is
// still pressed at the stop and can only be released by moving away from it.
static void TestHomeSwitchAtHardStop() {
  for (int on_switch = 0; on_switch < 2; ++on_switch) {
    std::printf("home: switch pressed up to the hard stop (%s)\n", on_switch ? "starting on it" : "starting below it");
    Rig r;
    r.sim.switch_at[kShoulder] = 129.5f;  // pressed from 128.5 deg to past the 130 deg stop
    float jc[kJoints];
    SimArm::ToJoints(r.sim.mcount, jc);
    jc[kShoulder] = (on_switch ? 129.8f : 60.f) * r.sim.true_cpu[kShoulder];
    SimArm::ToMotors(jc, r.sim.mcount);
    r.run(0.05f);
    CHECK(r.robot.status().sw[kShoulder] == (on_switch != 0), "switch state at start");
    r.robot.enable();
    r.robot.home(kShoulder);
    CHECK(r.run(120.f, [&] { return r.robot.status().mode != Mode::kHoming; }), "timeout");
    CHECK(r.robot.status().homed[kShoulder], "shoulder not homed, fault '%s'", r.robot.status().fault);
    // zero is the switch edge reached creeping in home_dir (-1): its low edge
    CHECK(std::fabs(r.sim.jointDeg(kShoulder) - 128.5f) < 0.5f, "homed at %.2f deg", r.sim.jointDeg(kShoulder));
  }
}

static void TestCalibrate() {
  std::puts("calibrate: travel span gives counts/deg");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  CHECK(r.robot.calibrate(kShoulder), "%s", r.robot.lastError());
  CHECK(r.run(240.f, [&] { return r.robot.status().mode != Mode::kCalibrating; }), "calibration timed out");
  const CalibResult& c = r.robot.calibResult(kShoulder);
  CHECK(c.result == Result::kPass, "result %s note '%s' fault '%s'", ResultName(c.result), c.note,
        r.robot.status().fault);
  float err = (c.counts_per_unit - r.sim.true_cpu[kShoulder]) / r.sim.true_cpu[kShoulder];
  CHECK(std::fabs(err) < 0.03f, "cpu %.1f vs true %.1f", c.counts_per_unit, r.sim.true_cpu[kShoulder]);
  CHECK(r.robot.applyCalibration(kShoulder), "%s", r.robot.lastError());
  // After applying, the reported angle should match the sim's true angle.
  r.run(0.5f);
  float d = r.robot.status().pos[kShoulder] - r.sim.jointDeg(kShoulder);
  CHECK(std::fabs(d) < 1.5f, "reported %.2f vs true %.2f", r.robot.status().pos[kShoulder], r.sim.jointDeg(kShoulder));
  // Roll has no stops and must be skipped.
  r.robot.calibrate(kRoll);
  CHECK(r.robot.calibResult(kRoll).result == Result::kSkipped, "roll should be skipped");
}

static void TestCalibrateGripper() {
  std::puts("calibrate: gripper close/open span");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  CHECK(r.robot.calibrate(kGripper), "%s", r.robot.lastError());
  CHECK(r.run(120.f, [&] { return r.robot.status().mode != Mode::kCalibrating; }), "timed out");
  const CalibResult& c = r.robot.calibResult(kGripper);
  CHECK(c.result == Result::kPass, "result %s '%s' fault '%s'", ResultName(c.result), c.note, r.robot.status().fault);
  CHECK(std::fabs(c.counts_per_unit - r.sim.true_cpu[kGripper]) / r.sim.true_cpu[kGripper] < 0.03f, "cpu %.1f",
        c.counts_per_unit);
}

static void TestMotorTestFindsReversedMotor() {
  std::puts("test: motor test flags a reversed motor, flip fixes it");
  Rig r;
  r.sim.motor_polarity[kElbow] = -1;
  r.run(0.05f);
  r.robot.enable();
  CHECK(r.robot.testMotor(kElbow), "%s", r.robot.lastError());
  CHECK(r.run(5.f, [&] { return r.robot.status().mode != Mode::kTest; }), "test timed out");
  CHECK(r.robot.motorTest(kElbow).result == Result::kWarn, "result %s '%s'",
        ResultName(r.robot.motorTest(kElbow).result), r.robot.motorTest(kElbow).note);
  r.robot.flipMotorDir(kElbow);
  r.robot.testMotor(kElbow);
  r.run(5.f, [&] { return r.robot.status().mode != Mode::kTest; });
  CHECK(r.robot.motorTest(kElbow).result == Result::kPass, "after flip: %s '%s'",
        ResultName(r.robot.motorTest(kElbow).result), r.robot.motorTest(kElbow).note);
}

static void TestSelfTest() {
  std::puts("test: self-test passes all motors, flags a jammed one");
  Rig r;
  r.sim.jammed[kGripper] = true;
  r.run(0.05f);
  r.robot.enable();
  CHECK(r.robot.selfTest(), "%s", r.robot.lastError());
  CHECK(r.run(20.f, [&] { return r.robot.status().mode != Mode::kTest; }), "self-test timed out");
  for (int m = 0; m < kGripper; ++m)
    CHECK(r.robot.motorTest(m).result == Result::kPass, "motor %d: %s '%s'", m, ResultName(r.robot.motorTest(m).result),
          r.robot.motorTest(m).note);
  CHECK(r.robot.motorTest(kGripper).result == Result::kFail, "jammed gripper: %s",
        ResultName(r.robot.motorTest(kGripper).result));
  CHECK(r.robot.status().enabled, "should stay enabled after the self-test");
}

static void TestEStopAndFaults() {
  std::puts("safety: E-stop latch, jog timeout, following error");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  r.sim.vm = false;
  r.run(0.05f);
  CHECK(r.robot.status().mode == Mode::kEStop, "mode %s", ModeName(r.robot.status().mode));
  CHECK(!r.robot.enable(), "enable must be refused while latched");
  r.sim.vm = true;
  CHECK(r.robot.resetFault(), "%s", r.robot.lastError());
  CHECK(r.robot.enable(), "%s", r.robot.lastError());

  r.robot.jog(kBase, 0.5f);
  r.run(0.1f);
  CHECK(r.robot.status().mode == Mode::kJog, "jogging");
  r.run(1.0f);  // no heartbeat: must stop by itself
  CHECK(r.robot.status().mode == Mode::kIdle, "jog should time out, mode %s", ModeName(r.robot.status().mode));

  r.sim.jammed[kBase] = true;
  float tgt[kJoints] = {};
  bool use[kJoints] = {};
  tgt[kBase] = r.robot.status().pos[kBase] + 40.f;
  use[kBase] = true;
  r.robot.moveTo(tgt, use, 1.f);
  r.run(5.f, [&] { return r.robot.status().mode == Mode::kFault; });
  CHECK(r.robot.status().mode == Mode::kFault, "jam should fault, mode %s", ModeName(r.robot.status().mode));
  CHECK(std::strstr(r.robot.status().fault, "following") != nullptr, "fault '%s'", r.robot.status().fault);
}

static void TestFaultFiltering() {
  std::puts("safety: brief VM / nFAULT glitches are ignored, sustained ones latch");
  Rig r;
  r.run(0.05f);
  CHECK(r.robot.enable(), "%s", r.robot.lastError());
  r.sim.fault = true;   // nFAULT right after wake (charge pump starting)
  r.run(0.008f);
  r.sim.fault = false;
  r.run(0.05f);
  CHECK(r.robot.status().mode != Mode::kFault, "wake glitch faulted: '%s'", r.robot.status().fault);
  r.sim.vm = false;     // a 10 ms dip
  r.run(0.010f);
  r.sim.vm = true;
  r.run(0.05f);
  CHECK(r.robot.status().mode != Mode::kEStop, "10 ms VM dip latched E-stop");
  r.sim.fault = true;   // a 3 ms nFAULT pulse
  r.run(0.003f);
  r.sim.fault = false;
  r.run(0.05f);
  CHECK(r.robot.status().mode != Mode::kFault, "3 ms nFAULT pulse faulted: '%s'", r.robot.status().fault);
  r.sim.fault = true;   // a real driver fault
  r.run(0.05f);
  CHECK(std::strstr(r.robot.status().fault, "nFAULT") != nullptr, "sustained nFAULT: '%s'", r.robot.status().fault);
  r.sim.fault = false;
  CHECK(r.robot.resetFault(), "%s", r.robot.lastError());
  CHECK(r.robot.enable(), "%s", r.robot.lastError());
  r.sim.vm = false;     // a real E-stop
  r.run(0.05f);
  CHECK(r.robot.status().mode == Mode::kEStop, "sustained VM loss: mode %s", ModeName(r.robot.status().mode));
}

static void TestOverCurrent() {
  std::printf("safety: sustained current near the %s limit trips, brief peaks don't\n", kDriverName);
  const float high = kDefaultTripA + 0.1f;
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  r.sim.extra_amps[kElbow] = high;
  r.run(0.8f);
  CHECK(r.robot.status().mode != Mode::kFault, "tripped early: '%s'", r.robot.status().fault);
  r.sim.extra_amps[kElbow] = 0;
  r.run(0.3f);
  r.sim.extra_amps[kElbow] = high;
  r.run(1.2f);
  CHECK(std::strstr(r.robot.status().fault, "over-current on motor 3") != nullptr, "fault '%s'", r.robot.status().fault);
  // Enabling again clears the fault: no separate reset step.
  r.sim.extra_amps[kElbow] = 0;
  CHECK(r.robot.enable(), "re-enable after fault: %s", r.robot.lastError());
  CHECK(r.robot.status().mode != Mode::kFault && r.robot.status().enabled, "mode %s", ModeName(r.robot.status().mode));
}

static void TestHandCalibrate() {
  std::puts("hand calibration: motors off, move a joint end to end by hand");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  CHECK(!r.robot.handBegin(kShoulder), "must refuse while enabled");
  r.robot.disable();
  // Moves the shoulder by hand (motors off) to deg, in small steps.
  auto handTo = [&](float deg) {
    float jc[kJoints];
    for (int i = 0; i < 400; ++i) {
      SimArm::ToJoints(r.sim.mcount, jc);
      const float cur = jc[kShoulder] / r.sim.true_cpu[kShoulder];
      const float step = std::max(-0.5f, std::min(0.5f, deg - cur));
      if (std::fabs(step) < 1e-4f) break;
      jc[kShoulder] += step * r.sim.true_cpu[kShoulder];
      SimArm::ToMotors(jc, r.sim.mcount);
      r.run(0.005f);
    }
  };
  CHECK(r.robot.handBegin(kShoulder), "%s", r.robot.lastError());
  handTo(r.sim.stop_min[kShoulder]);
  CHECK(r.robot.handMark(kShoulder, 0), "%s", r.robot.lastError());
  CHECK(!r.robot.handFinish(kShoulder), "finish needs both ends");
  handTo(r.sim.stop_max[kShoulder]);
  CHECK(r.robot.handMark(kShoulder, 1), "%s", r.robot.lastError());
  CHECK(r.robot.handFinish(kShoulder), "%s", r.robot.lastError());
  const CalibResult& c = r.robot.calibResult(kShoulder);
  const float err = (c.counts_per_unit - r.sim.true_cpu[kShoulder]) / r.sim.true_cpu[kShoulder];
  CHECK(std::fabs(err) < 0.02f, "cpu %.1f vs true %.1f", c.counts_per_unit, r.sim.true_cpu[kShoulder]);
  CHECK(r.robot.status().homed[kShoulder], "should be homed");
  handTo(70.f);
  r.run(0.05f);
  CHECK(std::fabs(r.robot.status().pos[kShoulder] - 70.f) < 1.f, "reads %.2f, true 70", r.robot.status().pos[kShoulder]);
  // Its switch zero matches what homing finds: the low edge of the switch (home_dir -1).
  const float edge = r.sim.switch_at[kShoulder] - r.sim.switch_width / 2;
  CHECK(std::fabs(c.home_pos - edge) < 1.f, "switch at %.2f, true edge %.2f", c.home_pos, edge);
  // Missing the switch is refused.
  CHECK(r.robot.handBegin(kElbow), "%s", r.robot.lastError());
  CHECK(r.robot.handMark(kElbow, 0), "%s", r.robot.lastError());
  float jc[kJoints];
  SimArm::ToJoints(r.sim.mcount, jc);
  jc[kElbow] += 5000;
  SimArm::ToMotors(jc, r.sim.mcount);
  r.run(0.01f);
  CHECK(r.robot.handMark(kElbow, 1), "%s", r.robot.lastError());
  CHECK(!r.robot.handFinish(kElbow), "should fail without the switch");

  // Roll: mark "flat", turn one full turn, mark again. No switch needed, and
  // the flat mark reads 0 deg afterwards.
  auto turnRoll = [&](float deg) {
    float jr[kJoints];
    for (int i = 0; i < 2000 && std::fabs(deg) > 1e-4f; ++i) {
      const float step = std::max(-0.5f, std::min(0.5f, deg));
      SimArm::ToJoints(r.sim.mcount, jr);
      jr[kRoll] += step * r.sim.true_cpu[kRoll];
      SimArm::ToMotors(jr, r.sim.mcount);
      r.run(0.002f);
      deg -= step;
    }
  };
  turnRoll(37.f);  // flat is wherever the user says it is
  CHECK(r.robot.handBegin(kRoll), "%s", r.robot.lastError());
  CHECK(r.robot.handMark(kRoll, 0), "%s", r.robot.lastError());
  turnRoll(-360.f);
  CHECK(r.robot.handMark(kRoll, 1), "%s", r.robot.lastError());
  CHECK(r.robot.handFinish(kRoll), "%s", r.robot.lastError());
  const float rerr = (r.robot.calibResult(kRoll).counts_per_unit - r.sim.true_cpu[kRoll]) / r.sim.true_cpu[kRoll];
  CHECK(std::fabs(rerr) < 0.02f, "roll cpu %.2f vs true %.2f", r.robot.calibResult(kRoll).counts_per_unit, r.sim.true_cpu[kRoll]);
  CHECK(r.robot.status().homed[kRoll], "roll should be homed");
  CHECK(!r.cfg.joint[kRoll].has_switch, "roll is hand-zeroed from now on");
  turnRoll(360.f + 90.f);  // back to flat, then 90 more
  r.run(0.05f);
  CHECK(std::fabs(std::fabs(r.robot.status().pos[kRoll]) - 90.f) < 2.f, "roll reads %.2f, want 90 from flat", r.robot.status().pos[kRoll]);

  // Gripper: calibrated with the motors on (jogged), not by hand.
  r.robot.enable();
  CHECK(r.robot.handBegin(kGripper), "gripper hand calibration with motors on: %s", r.robot.lastError());
  CHECK(!r.robot.handBegin(kShoulder), "other joints must refuse while enabled");
  CHECK(!r.robot.home(kRoll), "roll has no switch now: homing it alone is refused");
}

static void TestDifferentialWrist() {
  std::puts("wrist: pitch-only move drives the two wrist motors opposite ways");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  const int32_t a0 = r.robot.status().counts[3], b0 = r.robot.status().counts[4];
  float tgt[kJoints] = {};
  bool use[kJoints] = {};
  tgt[kPitch] = r.robot.status().pos[kPitch] + 20.f;
  use[kPitch] = true;
  r.robot.moveTo(tgt, use, 1.f);
  r.run(10.f, [&] { return r.idle(); });
  const int32_t da = r.robot.status().counts[3] - a0, db = r.robot.status().counts[4] - b0;
  CHECK(da > 100 && db < -100 && std::abs(da + db) < 30, "da %d db %d", da, db);
}

static void TestWristSign() {
  std::puts("wrist: reversing pitch/roll flips only the kinematics, not the motors");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  float tgt[kJoints] = {};
  bool use[kJoints] = {};
  tgt[kPitch] = r.robot.status().pos[kPitch] + 15.f;
  tgt[kRoll] = r.robot.status().pos[kRoll] + 25.f;
  use[kPitch] = use[kRoll] = true;
  r.robot.moveTo(tgt, use, 1.f);
  r.run(10.f, [&] { return r.idle(); });
  r.run(0.3f);
  const float p0 = r.robot.status().pos[kPitch], q0 = r.robot.status().pos[kRoll];
  const int md3 = r.cfg.motor[3].motor_dir, ed3 = r.cfg.motor[3].enc_dir;
  const int32_t a0 = r.robot.status().counts[3], b0 = r.robot.status().counts[4];
  r.robot.invertJoint(kPitch);
  r.run(0.5f);
  CHECK(r.cfg.pitch_sign == -1 && r.cfg.roll_sign == 1, "signs %d %d", r.cfg.pitch_sign, r.cfg.roll_sign);
  CHECK(r.cfg.motor[3].motor_dir == md3 && r.cfg.motor[3].enc_dir == ed3, "motor dirs changed");
  CHECK(std::abs(r.robot.status().counts[3] - a0) < 30 && std::abs(r.robot.status().counts[4] - b0) < 30,
        "wrist moved on invert: %d %d", (int)(r.robot.status().counts[3] - a0), (int)(r.robot.status().counts[4] - b0));
  CHECK(std::fabs(r.robot.status().pos[kPitch] + p0) < 0.5f, "pitch %.2f vs %.2f", r.robot.status().pos[kPitch], p0);
  CHECK(std::fabs(r.robot.status().pos[kRoll] - q0) < 0.5f, "roll %.2f vs %.2f", r.robot.status().pos[kRoll], q0);
  CHECK(r.robot.status().mode == Mode::kIdle, "mode %s %s", ModeName(r.robot.status().mode), r.robot.lastError());
  // A positive pitch move now turns motor 3 backwards and motor 4 forwards.
  const int32_t a1 = r.robot.status().counts[3], b1 = r.robot.status().counts[4];
  tgt[kPitch] = r.robot.status().pos[kPitch] + 20.f;
  tgt[kRoll] = r.robot.status().pos[kRoll];
  r.robot.moveTo(tgt, use, 1.f);
  r.run(10.f, [&] { return r.idle(); });
  const int da = (int)(r.robot.status().counts[3] - a1), db = (int)(r.robot.status().counts[4] - b1);
  CHECK(da < -100 && db > 100 && std::abs(da + db) < 30, "da %d db %d", da, db);
  r.robot.invertJoint(kRoll);
  r.run(0.2f);
  CHECK(r.cfg.roll_sign == -1, "roll sign %d", r.cfg.roll_sign);
}

static void TestGripperParks() {
  std::puts("gripper: parks with the motor off once it reaches its target");
  Rig r;
  r.run(0.05f);
  r.robot.enable();
  float tgt[kJoints] = {};
  bool use[kJoints] = {};
  tgt[kGripper] = r.robot.status().pos[kGripper] + 5.f;
  use[kGripper] = true;
  r.robot.moveTo(tgt, use, 1.f);
  r.run(10.f, [&] { return r.idle(); });
  r.run(0.3f);
  int driven = 0;
  for (int i = 0; i < 1000; ++i) {
    r.run(0.001f);
    if (r.robot.status().duty[kGripper] != 0) ++driven;
  }
  CHECK(driven == 0, "gripper driven %d of 1000 ms at rest", driven);
  CHECK(std::fabs(r.robot.status().pos[kGripper] - tgt[kGripper]) < 0.6f, "gripper error %.2f mm",
        r.robot.status().pos[kGripper] - tgt[kGripper]);
}

int main() {
  TestEnableAndMove();
  TestHomeAll();
  TestHomeFromOnSwitch();
  TestHomeSwitchAtHardStop();
  TestCalibrate();
  TestCalibrateGripper();
  TestMotorTestFindsReversedMotor();
  TestSelfTest();
  TestEStopAndFaults();
  TestFaultFiltering();
  TestOverCurrent();
  TestHandCalibrate();
  TestDifferentialWrist();
  TestWristSign();
  TestGripperParks();
  std::printf("\n%d checks passed, %d failed\n", g_pass, g_fail);
  return g_fail ? 1 : 0;
}

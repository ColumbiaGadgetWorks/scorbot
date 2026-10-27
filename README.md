# Scorbot ER-4u ESP32 controller

A replacement controller for the Intelitek Scorbot ER-4u robot arm. An ESP32
drives the arm's six DC motors and reads its encoders and home switches. A web
UI (WiFi, with an access-point fallback) gives jogging, a live 3D view,
self-tests, homing and travel calibration, and there is a JSON HTTP/WebSocket
API.

| Folder | What's in it |
| --- | --- |
| [`hardware/scorbot-controller/`](hardware/scorbot-controller/) | KiCad 7 project for the master board, generated from Python (`generator/design.py`), autorouted, with JLCPCB fab files in `fab/` |
| [`firmware/`](firmware/) | ESP-IDF 5.3+ firmware, the single-file web UI, and host-side tests on a simulated arm |
| [`flasher/`](flasher/) | Guided web firmware installer: open <https://columbiagadgetworks.github.io/scorbot/> in Chrome or Edge and flash over USB |

The board takes an ESP32-DevKitC (WROOM-32D or -32E), six motor driver
carriers and a DROK 5 V buck module on headers. The carriers are the DRV8874
board in [`hardware/drv8874-carrier/`](hardware/drv8874-carrier/), or
Pololu's #4035 (DRV8874) or #4036 (DRV8876), picked with one menuconfig
setting in the firmware. The
robot's DB-50 cable plugs straight in. JLCPCB places the SMD parts (passives,
LEDs, the TCA9555 I/O expander and two ADS1115 ADCs); the connectors, sockets
and big capacitors are through-hole and hand-soldered.

**Status:** the board has not been ordered or tested, and the firmware has not run on
hardware. Read "Must check before ordering boards" in the
[hardware README](hardware/scorbot-controller/README.md) before ordering.

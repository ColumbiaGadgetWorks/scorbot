# Firmware installer

A local web page that flashes the controller firmware onto the ESP32 DevKit
over USB, with a guided, step-by-step process (like the WLED or Meshtastic
web flashers). It uses [ESP Web Tools](https://github.com/esphome/esp-web-tools),
included in `vendor/`, so it works offline once the firmware is downloaded.

## Use it

You need Python 3 and **Chrome or Edge** on a desktop computer (Firefox and
Safari have no Web Serial).

```
python3 flasher/serve.py
```

That opens http://localhost:8484. The page walks you through:

1. Checking the browser.
2. Picking your motor drivers: the CGW DRV8874 carrier, Pololu #4035 or
   Pololu #4036. Each has its own firmware build.
3. Getting the controller ready: motor power off, USB cable in.
4. Installing. Click **Connect**, pick the port, then **Install**. Erase on
   a first install only; erasing also deletes Wi-Fi settings and calibration.
5. Joining the controller's `Scorbot-XXXX` Wi-Fi and setting it up.
6. First run: self-test, switches, calibration, homing.

## Where the firmware comes from

`serve.py` serves whatever is in `flasher/firmware/` (not in git). If that's
empty it downloads the latest build:

- GitHub Actions (`.github/workflows/firmware.yml`) builds all three variants
  on every push to `main` that touches the firmware, and publishes them as
  the `firmware-latest` release (`scorbot-firmware.zip`).
- `python3 flasher/serve.py --download` fetches it again. For a private
  repository, set `GITHUB_TOKEN`, or have the `gh` CLI logged in.
- `python3 flasher/serve.py --zip scorbot-firmware.zip` uses a zip you
  downloaded by hand.
- `python3 flasher/serve.py --build` builds locally with ESP-IDF 5.3+
  (`idf.py` on PATH) or, failing that, Docker (`espressif/idf:v5.3.2`).

Each variant is flashed as three parts (bootloader at 0x1000, partition
table at 0x8000, app at 0x10000) rather than one merged image. That way an
update that doesn't erase keeps the NVS partition, where the Wi-Fi settings
and calibration live.

## Files

| File | What it is |
|---|---|
| `index.html` | The guided installer page |
| `serve.py` | Local web server, plus firmware download/build |
| `build_firmware.py` | Builds every driver variant and writes `firmware/` (also used by CI) |
| `vendor/esp-web-tools/` | ESP Web Tools 10.4.0 browser bundle (Apache-2.0) |

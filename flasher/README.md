# Firmware installer

A local web page that flashes the controller firmware onto the ESP32 DevKit
over USB, with a guided, step-by-step process (like the WLED or Meshtastic
web flashers). It uses [ESP Web Tools](https://github.com/esphome/esp-web-tools),
included in `vendor/`, so it works offline once the firmware is downloaded.

## Use it

1. Download the installer for your computer from the
   [`firmware-latest` release](https://github.com/ColumbiaGadgetWorks/scorbot/releases/tag/firmware-latest):
   - **Windows:** `ScorbotFlasher-windows.exe`. Double-click it. It isn't
     code-signed, so Windows SmartScreen may say "Windows protected your PC":
     click **More info**, then **Run anyway**.
   - **Linux:** `ScorbotFlasher-linux.tar.gz`. Unpack it and run
     `./ScorbotFlasher`. You may need to be in the `dialout` group for USB
     serial access.
   - **macOS:** `ScorbotFlasher-macos.zip`. Unzip it, then right-click
     `ScorbotFlasher` and choose **Open** the first time (it isn't notarized).
2. A small window opens showing the address, and your browser opens
   http://localhost:8484. Use **Chrome or Edge** (Firefox and Safari have no
   Web Serial). Leave the window open while you install, and close it when
   you're done.

Each app has the firmware from the same build inside, so it works offline.
To pick up a newer build without downloading a new app, run it from a
terminal with `--download`.

From a checkout of the repository you can run the same thing with Python 3:
`python3 flasher/serve.py`.

The page walks you through:

1. Checking the browser.
2. Picking your motor drivers: the CGW DRV8874 carrier, Pololu #4035 or
   Pololu #4036. Each has its own firmware build.
3. Getting the controller ready: motor power off, USB cable in.
4. Installing. Click **Connect**, pick the port, then **Install**. Erase on
   a first install only; erasing also deletes Wi-Fi settings and calibration.
5. Joining the controller's `Scorbot-XXXX` Wi-Fi and setting it up.
6. First run: self-test, switches, calibration, homing.

## Where the firmware comes from

The app serves the firmware built into it, or a newer one fetched with
`--download` (kept in `%LOCALAPPDATA%\ScorbotFlasher` or
`~/.cache/ScorbotFlasher`). From a checkout, `serve.py` serves
`flasher/firmware/` (not in git), downloading the latest build if that's
empty:

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
| `serve.py` | Local web server, plus firmware download/build; this is the app's program |
| `build_app.py` | Packages `serve.py`, the page and `firmware/` into one program with PyInstaller (CI runs it on Windows, Linux and macOS) |
| `build_firmware.py` | Builds every driver variant and writes `firmware/` (also used by CI) |
| `vendor/esp-web-tools/` | ESP Web Tools 10.4.0 browser bundle (Apache-2.0) |

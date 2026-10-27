"""Build the firmware for each motor-driver variant and lay it out for the
web flasher.

    python3 flasher/build_firmware.py            # uses idf.py if it's on PATH, else Docker
    python3 flasher/build_firmware.py --docker   # force the espressif/idf container
    python3 flasher/build_firmware.py --zip dist/scorbot-firmware.zip   # also zip it (CI)

Output (default flasher/firmware/):
    index.json                     version, build time and the variant list (read by index.html)
    <variant>/manifest.json        ESP Web Tools manifest
    <variant>/bootloader.bin, partition-table.bin, scorbot_controller.bin

The parts are flashed at their own offsets, not as one merged image, so an
update without "erase" keeps the NVS partition (Wi-Fi and calibration).
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FW = os.path.join(REPO, "firmware")
IMAGE = "espressif/idf:v5.3.2"

# id, name, how to recognise it, Kconfig line (see firmware/main/Kconfig.projbuild)
VARIANTS = [
    ("cgw", "CGW DRV8874 carrier",
     "The carrier from hardware/drv8874-carrier (\"DRV8874 CGW\" on the back). CS 1.08 V/A, about 3.1 A limit.",
     "CONFIG_SCORBOT_DRIVER_CGW=y"),
    ("pololu4035", "Pololu #4035 (DRV8874)",
     "Pololu carrier with \"8874\" on the chip. CS 1.12 V/A, about 2.9 A limit.",
     "CONFIG_SCORBOT_DRIVER_POLOLU_4035=y"),
    ("pololu4036", "Pololu #4036 (DRV8876)",
     "Pololu carrier with \"8876\" on the chip. CS 2.49 V/A, about 1.3 A limit.",
     "CONFIG_SCORBOT_DRIVER_POLOLU_4036=y"),
]


def git_version():
    try:
        return subprocess.run(["git", "-C", REPO, "describe", "--tags", "--always", "--dirty"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return datetime.date.today().isoformat()


def build_variant(vid, kconfig, out):
    bdir = os.path.join(FW, "build_flasher", vid)
    os.makedirs(bdir, exist_ok=True)
    extra = os.path.join(bdir, "variant.defaults")
    with open(extra, "w") as f:
        f.write(kconfig + "\n")
    subprocess.run(["idf.py", "-C", FW, "-B", bdir, f"-DSDKCONFIG={os.path.join(bdir, 'sdkconfig')}",
                    f"-DSDKCONFIG_DEFAULTS={os.path.join(FW, 'sdkconfig.defaults')};{extra}", "build"], check=True)
    args = json.load(open(os.path.join(bdir, "flasher_args.json")))
    parts = []
    for offset, path in sorted(args["flash_files"].items(), key=lambda kv: int(kv[0], 16)):
        name = ("bootloader.bin" if "bootloader" in path else
                "partition-table.bin" if "partition" in path else os.path.basename(path))
        shutil.copy(os.path.join(bdir, path), os.path.join(out, vid, name))
        parts.append({"path": name, "offset": int(offset, 16)})
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "firmware"))
    ap.add_argument("--zip", help="also write the output folder into this zip")
    ap.add_argument("--docker", action="store_true", help="build inside the espressif/idf container")
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--version", default=None)
    a = ap.parse_args()
    version = a.version or git_version()
    out = os.path.abspath(a.out)

    if a.docker or not shutil.which("idf.py"):
        if not shutil.which("docker"):
            sys.exit("Needs ESP-IDF 5.3+ (idf.py on PATH, after running export.sh) or Docker.")
        rel_out = os.path.relpath(out, REPO)
        if rel_out.startswith(".."):
            sys.exit("--out must be inside the repository when building with Docker")
        cmd = ["docker", "run", "--rm", "-v", f"{REPO}:/repo", "-w", "/repo", a.image,
               "python3", "flasher/build_firmware.py", "--out", rel_out, "--version", version]
        if a.zip:
            cmd += ["--zip", os.path.relpath(os.path.abspath(a.zip), REPO)]
        print("building in", a.image)
        sys.exit(subprocess.run(cmd).returncode)

    shutil.rmtree(out, ignore_errors=True)
    index = {"version": version, "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
             "chip": "ESP32", "variants": []}
    for vid, name, desc, kconfig in VARIANTS:
        os.makedirs(os.path.join(out, vid))
        parts = build_variant(vid, kconfig, out)
        manifest = {
            "name": f"Scorbot ER-4u controller - {name}",
            "version": version,
            "new_install_prompt_erase": True,
            "new_install_improv_wait_time": 0,   # the firmware doesn't speak Improv
            "builds": [{"chipFamily": "ESP32", "parts": parts}],
        }
        with open(os.path.join(out, vid, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        size = sum(os.path.getsize(os.path.join(out, vid, p["path"])) for p in parts)
        index["variants"].append({"id": vid, "name": name, "description": desc,
                                  "manifest": f"firmware/{vid}/manifest.json", "bytes": size})
        print(f"{vid}: {size} bytes")
    with open(os.path.join(out, "index.json"), "w") as f:
        json.dump(index, f, indent=2)
    if a.zip:
        os.makedirs(os.path.dirname(os.path.abspath(a.zip)), exist_ok=True)
        with zipfile.ZipFile(a.zip, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(out):
                for f in files:
                    full = os.path.join(root, f)
                    z.write(full, os.path.join("firmware", os.path.relpath(full, out)))
        print("zipped to", a.zip)
    print(f"firmware {version} -> {out}")


if __name__ == "__main__":
    main()

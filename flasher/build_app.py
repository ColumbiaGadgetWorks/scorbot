"""Package the installer as one double-clickable program with PyInstaller.

    pip install pyinstaller
    python3 flasher/build_firmware.py           # (or unzip a CI build into flasher/firmware/)
    python3 flasher/build_app.py                # -> flasher/dist/ScorbotFlasher[.exe]

Build on each OS for that OS (PyInstaller can't cross-compile); CI does
Windows, Linux and macOS. The page, ESP Web Tools and the firmware in
flasher/firmware/ are built in, so the app works offline.
"""
import os
import sys

import PyInstaller.__main__

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.join(HERE, "firmware")


def main():
    if not os.path.exists(os.path.join(FW, "index.json")):
        sys.exit("flasher/firmware/ is empty: build the firmware first (build_firmware.py), "
                 "or unzip scorbot-firmware.zip there.")
    sep = os.pathsep        # PyInstaller's --add-data separator is ';' on Windows, ':' elsewhere
    PyInstaller.__main__.run([
        os.path.join(HERE, "serve.py"),
        "--onefile",
        "--console",                       # the window shows the address and how to stop it
        "--name", "ScorbotFlasher",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        "--add-data", f"{os.path.join(HERE, 'index.html')}{sep}.",
        "--add-data", f"{os.path.join(HERE, 'vendor')}{sep}vendor",
        "--add-data", f"{FW}{sep}firmware",
        "--noconfirm",
    ])


if __name__ == "__main__":
    main()

"""Run the Scorbot firmware installer on this computer, offline.

Normally you don't need this: the same installer, with the latest firmware,
is at https://columbiagadgetworks.github.io/scorbot/ . From a checkout:

    python3 flasher/serve.py              # serve, opening http://localhost:8484 in your browser
    python3 flasher/serve.py --download   # fetch the latest firmware build from GitHub first
    python3 flasher/serve.py --build      # build the firmware locally first (ESP-IDF or Docker)
    python3 flasher/serve.py --zip FILE   # use a scorbot-firmware.zip you downloaded

Flashing happens in the browser over Web Serial, so use Chrome or Edge on a
desktop. The page has to come from localhost (or HTTPS) for the browser to
allow serial access, which is why it's served rather than opened as a file.
"""
import argparse
import http.server
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "ColumbiaGadgetWorks/scorbot"
TAG = "firmware-latest"
ASSET = "scorbot-firmware.zip"


FW_WRITABLE = os.path.join(HERE, "firmware")


def firmware_dir():
    return FW_WRITABLE if os.path.exists(os.path.join(FW_WRITABLE, "index.json")) else None


def unpack(data):
    tmp = tempfile.mkdtemp()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(tmp)                         # the zip holds firmware/...
    shutil.rmtree(FW_WRITABLE, ignore_errors=True)
    os.makedirs(os.path.dirname(FW_WRITABLE), exist_ok=True)
    shutil.move(os.path.join(tmp, "firmware"), FW_WRITABLE)
    shutil.rmtree(tmp, ignore_errors=True)
    version = json.load(open(os.path.join(FW_WRITABLE, "index.json"))).get("version", "?")
    print(f"firmware {version} unpacked to {FW_WRITABLE}")
    return True


def download():
    """Latest CI build: public download first, then the GitHub API with a
    token (GITHUB_TOKEN / GH_TOKEN) or the gh CLI, for a private repository."""
    url = f"https://github.com/{REPO}/releases/download/{TAG}/{ASSET}"
    try:
        print("downloading", url)
        with urllib.request.urlopen(url, timeout=60) as r:
            return unpack(r.read())
    except Exception as e:  # noqa: BLE001
        print("  not available publicly:", e)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        try:
            api = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
            req = urllib.request.Request(api, headers={"Authorization": f"Bearer {token}"})
            rel = json.load(urllib.request.urlopen(req, timeout=60))
            asset = next(a for a in rel["assets"] if a["name"] == ASSET)
            req = urllib.request.Request(asset["url"], headers={"Authorization": f"Bearer {token}",
                                                                "Accept": "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return unpack(r.read())
        except Exception as e:  # noqa: BLE001
            print("  API download failed:", e)
    if shutil.which("gh"):
        tmp = tempfile.mkdtemp()
        r = subprocess.run(["gh", "release", "download", TAG, "-R", REPO, "-p", ASSET, "-D", tmp])
        if r.returncode == 0:
            data = open(os.path.join(tmp, ASSET), "rb").read()
            shutil.rmtree(tmp, ignore_errors=True)
            return unpack(data)
    print(f"Could not download the firmware. Download {ASSET} from the '{TAG}' release\n"
          f"on GitHub yourself and start this with:  --zip <that file>")
    return False


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves flasher/ (the page, vendor/ and firmware/)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # always serve the newest build
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def free_port(preferred):
    for port in [preferred] + list(range(preferred + 1, preferred + 20)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8484)
    ap.add_argument("--download", action="store_true", help="fetch the latest firmware build from GitHub")
    ap.add_argument("--build", action="store_true", help="build the firmware locally first (from a checkout)")
    ap.add_argument("--zip", help="use a downloaded scorbot-firmware.zip")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    if a.build:
        subprocess.run([sys.executable, os.path.join(HERE, "build_firmware.py")], check=True)
    elif a.zip:
        unpack(open(a.zip, "rb").read())
    elif a.download or firmware_dir() is None:
        download()
    fw = firmware_dir()
    if fw:
        idx = json.load(open(os.path.join(fw, "index.json")))
        print(f"Firmware {idx.get('version')} (built {idx.get('built')})")
    else:
        print("No firmware yet: the page will open, but there's nothing to install.")

    port = free_port(a.port)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{server.server_address[1]}/"
    print(f"\nScorbot firmware installer: {url}")
    print("Leave this window open while you install. Close it (or press Ctrl+C) when you're done.")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()

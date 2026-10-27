"""Run the Scorbot firmware installer on this computer.

    python3 flasher/serve.py              # serve, opening http://localhost:8484 in your browser
    python3 flasher/serve.py --download   # fetch the latest firmware build from GitHub first
    python3 flasher/serve.py --build      # build the firmware locally first (ESP-IDF or Docker)

Needs only Python 3. Flashing happens in the browser over Web Serial, so use
Chrome or Edge on a desktop. The page has to come from localhost (or HTTPS)
for the browser to allow serial access, which is why it's served rather than
opened as a file.

Firmware comes from flasher/firmware/. If it's missing, this script tries the
"firmware-latest" release that GitHub Actions publishes on every push to main.
"""
import argparse
import functools
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.join(HERE, "firmware")
REPO = "ColumbiaGadgetWorks/scorbot"
TAG = "firmware-latest"
ASSET = "scorbot-firmware.zip"


def have_firmware():
    return os.path.exists(os.path.join(FW, "index.json"))


def unpack(data):
    shutil.rmtree(FW, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(HERE)          # the zip holds firmware/...
    print("firmware unpacked to", FW)


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
        tmp = os.path.join(HERE, ".download")
        shutil.rmtree(tmp, ignore_errors=True)
        r = subprocess.run(["gh", "release", "download", TAG, "-R", REPO, "-p", ASSET, "-D", tmp])
        if r.returncode == 0:
            data = open(os.path.join(tmp, ASSET), "rb").read()
            shutil.rmtree(tmp, ignore_errors=True)
            return unpack(data)
    print("Could not download the firmware. Either build it (--build), or download\n"
          f"{ASSET} from the '{TAG}' release on GitHub and run: python3 flasher/serve.py --zip <file>")
    return None


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # always serve the newest build
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8484)
    ap.add_argument("--download", action="store_true", help="fetch the latest CI build first")
    ap.add_argument("--build", action="store_true", help="build the firmware locally first")
    ap.add_argument("--zip", help="use a downloaded scorbot-firmware.zip")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    if a.build:
        subprocess.run([sys.executable, os.path.join(HERE, "build_firmware.py")], check=True)
    elif a.zip:
        unpack(open(a.zip, "rb").read())
    elif a.download or not have_firmware():
        download()
    if not have_firmware():
        print("\nNo firmware yet: the page will open, but there's nothing to install.")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), functools.partial(Handler, directory=HERE))
    url = f"http://localhost:{a.port}/"
    print(f"\nScorbot firmware installer: {url}   (Ctrl+C to stop)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()

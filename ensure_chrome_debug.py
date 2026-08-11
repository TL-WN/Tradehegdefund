"""
ensure_chrome_debug.py
Self-healing launcher for the research desk's browser.
Checks if Chrome remote debugging is already up on 9222; if not, launches it
(headless-friendly background instance with a fixed debug profile).

Usage:  python ensure_chrome_debug.py
Exit 0 if a usable debugging endpoint is reachable (either already up or just launched).
Run this at the start of any cron job that needs live web (OPENING news scrape,
research web search) so the browser never dies between reboots.
"""
import json
import os
import subprocess
import sys
import urllib.request
import time

PORT = 9222
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_DIR = r"C:\Users\Eze\AppData\Local\hermes\chrome-debug"
VERSION_URL = f"http://127.0.0.1:{PORT}/json/version"


def _up():
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def launch():
    os.makedirs(DEBUG_DIR, exist_ok=True)
    args = [
        CHROME,
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={DEBUG_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "about:blank",
    ]
    # detached background process so it survives this script exiting
    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=0x00000008,  # DETACHED_PROCESS on Windows
    )


def main():
    if _up():
        print("Chrome debug already up on", PORT)
        return 0
    print("Chrome debug down — launching...")
    launch()
    # give it a few seconds to bind the port
    for _ in range(10):
        time.sleep(1)
        if _up():
            print("Chrome debug now up on", PORT)
            return 0
    print("ERROR: Chrome debug failed to start", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

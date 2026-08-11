"""
start_desk.py
Persistent launcher for the HERMES CAPITAL hedge-fund dashboard.
- Starts dashboard_app.py (local :8765)
- Starts a localtunnel; reads the public URL straight from localtunnel's stdout
  stream ("your url is: https://...loca.lt") and writes it to public_url.txt
- Self-heals: restarts dashboard or tunnel if either dies; re-saves URL on change.
Runs forever. Register with Windows Task Scheduler (see README) to survive reboots.
Current public link is always in public_url.txt.
"""
import os
import sys
import time
import subprocess
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
URL_FILE = os.path.join(HERE, "public_url.txt")
LT_JS = os.path.join(HERE, "node_modules", "localtunnel", "bin", "lt.js")
NODE = "node"


def url_alive(url):
    if not url:
        return False
    try:
        with urllib.request.urlopen(url + "/api/state", timeout=6) as r:
            return r.status == 200
    except Exception:
        return False


def start_tunnel():
    """Launch localtunnel, return (proc, url) once the url line appears on stdout."""
    proc = subprocess.Popen(
        [NODE, LT_JS, "--port", str(PORT)], cwd=HERE,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        close_fds=True, creationflags=0x00000008,
    )
    url = ""
    # read streaming stdout until we see the url line (or proc dies)
    import io
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode(errors="ignore")
        if "your url is:" in line:
            url = line.split("your url is:")[-1].strip()
            open(URL_FILE, "w").write(url)
            print("[launcher] PUBLIC URL:", url, "(saved to public_url.txt)")
            break
        if proc.poll() is not None:
            break
    return proc, url


def main():
    dash = None
    tunnel = None
    tunnel_url = ""
    last_check = 0
    print("HERMES CAPITAL desk launcher — starting (port %d)..." % PORT)
    while True:
        # dashboard
        if dash is None or dash.poll() is not None:
            print("[launcher] starting dashboard...")
            dash = subprocess.Popen(
                [sys.executable, "dashboard_app.py", str(PORT)], cwd=HERE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, creationflags=0x00000008,
            )
            time.sleep(3)

        # tunnel
        if tunnel is None or tunnel.poll() is not None:
            print("[launcher] starting localtunnel...")
            tunnel, tunnel_url = start_tunnel()

        # periodic liveness of the public url
        now = time.time()
        if now - last_check > 25:
            last_check = now
            if tunnel_url and not url_alive(tunnel_url):
                print("[launcher] public url down — restarting tunnel")
                try:
                    tunnel.terminate()
                except Exception:
                    pass
                tunnel = None
        time.sleep(15)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("stopped")

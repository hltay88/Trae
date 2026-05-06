import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
import shutil
import tempfile


_LOG_PATH = os.path.join(os.path.dirname(__file__), "desktop_app.log")


def _log(msg: str):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8", errors="ignore") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_port(host: str, port: int, timeout_s: float = 30.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def _start_streamlit(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    env.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        os.path.join(os.path.dirname(__file__), "bursa_web_app.py"),
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    _log(f"Starting Streamlit on 127.0.0.1:{port}")
    return subprocess.Popen(cmd, env=env)


def _open_in_webview(url: str) -> bool:
    try:
        import webview

        webview.create_window("Bursa Malaysia Breakout Analyzer", url, width=1280, height=800)
        webview.start()
        return True
    except Exception:
        return False


def _find_browser_app_exe() -> str | None:
    candidates = []
    env_edge = os.environ.get("BROWSER_APP_EXE")
    if env_edge:
        candidates.append(env_edge)

    for exe in ["msedge.exe", "chrome.exe"]:
        p = shutil.which(exe)
        if p:
            candidates.append(p)

    candidates.extend(
        [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    )

    for p in candidates:
        try:
            if p and Path(p).exists():
                return str(p)
        except Exception:
            continue
    return None


def _open_in_app_window(url: str) -> subprocess.Popen | None:
    try:
        exe = _find_browser_app_exe()
        if not exe:
            _log("No Edge/Chrome executable found for app window")
            return None
        profile_dir = tempfile.mkdtemp(prefix="bursa_desktop_profile_")
        cmd = [
            exe,
            f"--app={url}",
            "--window-size=1280,800",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile_dir}",
        ]
        _log(f"Launching app window: {exe} --app={url}")
        p = subprocess.Popen(cmd)
        setattr(p, "_bursa_profile_dir", profile_dir)
        return p
    except Exception:
        _log("Failed to launch app window")
        return None


def main() -> int:
    try:
        port = _pick_free_port()
        proc = _start_streamlit(port)
        url = f"http://127.0.0.1:{port}"
        try:
            if not _wait_port("127.0.0.1", port, timeout_s=45.0):
                _log("Streamlit port did not open in time")
                return 1

            if _open_in_webview(url):
                return 0

            app_proc = _open_in_app_window(url)
            if app_proc is None:
                _log("Falling back to default browser")
                webbrowser.open(url)

            print("\nBursa Desktop App is running.")
            print(f"URL: {url}")
            print("Close this window to exit (or press Ctrl+C).\n")
            try:
                proc.wait()
            except KeyboardInterrupt:
                pass

            try:
                if app_proc is not None:
                    profile_dir = getattr(app_proc, "_bursa_profile_dir", None)
                    if profile_dir:
                        shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                pass

            return 0
        finally:
            try:
                proc.terminate()
            except Exception:
                pass
    except Exception as e:
        _log(f"Fatal error: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


import subprocess, sys, time, socket, webbrowser, os
from pathlib import Path

ROOT = Path(__file__).parent
API_PORT = 8000
FE_PORT = 5173


def port_in_use(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return False
    except OSError:
        return True


def start_api():
    if port_in_use(API_PORT):
        print(f"  API already running on port {API_PORT}")
        return True
    print(f"  Starting API server on port {API_PORT}...")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(10):
        time.sleep(0.5)
        if port_in_use(API_PORT):
            print(f"  API started on http://127.0.0.1:{API_PORT}")
            return True
    print("  API failed to start")
    return False


def start_frontend():
    if port_in_use(FE_PORT):
        print(f"  Frontend already running on port {FE_PORT}")
        return True
    print(f"  Starting frontend on port {FE_PORT}...")
    fe_dir = ROOT / "frontend"
    node_modules = fe_dir / "node_modules"
    if not node_modules.exists():
        print("  Installing frontend dependencies (first run)...")
        subprocess.run(["npm", "install"], cwd=str(fe_dir), check=False)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.Popen(
        [npm, "exec", "vite", "--", "--host", "127.0.0.1", "--port", str(FE_PORT), "--strictPort"],
        cwd=str(fe_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(15):
        time.sleep(0.5)
        if port_in_use(FE_PORT):
            print(f"  Frontend started on http://127.0.0.1:{FE_PORT}")
            return True
    print("  Frontend failed to start")
    return False


def main():
    print("=" * 50)
    print("  Novel Forge v0.6.5")
    print("=" * 50)
    print()

    if not start_api():
        print("[FAIL] API server did not start")
        return 1

    if not start_frontend():
        print("[FAIL] Frontend did not start")
        return 1

    url = f"http://127.0.0.1:{FE_PORT}"
    print()
    print(f"  Opening browser: {url}")
    webbrowser.open(url)
    print()
    print("  Press Ctrl+C to stop all servers.")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down...")


if __name__ == "__main__":
    main()

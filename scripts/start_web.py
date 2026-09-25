"""Start the local web server independently of the invoking terminal/task."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    root = Path(__file__).resolve().parents[1]
    url = f"http://127.0.0.1:{args.port}"

    def healthy():
        try:
            with urlopen(url + "/api/workspace", timeout=2) as response:
                return response.status == 200
        except OSError:
            return False

    if healthy():
        print(f"ResearchPilot is already running: {url}")
        return
    folder = root / "tmp"
    folder.mkdir(exist_ok=True)
    log = folder / "web-server.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    with log.open("ab") as output:
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "researchpilot.web",
                "--root",
                str(root),
                "--port",
                str(args.port),
            ],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=output,
            start_new_session=True,
            close_fds=True,
        )
    for _ in range(40):
        if child.poll() is not None:
            raise SystemExit(f"Server did not start. See {log}")
        if healthy():
            (folder / "web-server.pid").write_text(str(child.pid))
            print(f"ResearchPilot running in background: {url} (PID {child.pid})")
            return
        time.sleep(0.25)
    raise SystemExit(f"Server startup is slow. Check {log} before starting again.")


if __name__ == "__main__":
    main()

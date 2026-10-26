import argparse
import asyncio
import os
import signal
import sys
import time
from pathlib import Path

from loguru import logger

from wvcr.config.env import OUTPUT, get_api_key
from wvcr.notification_manager import HyprlandNotificationManager

from .session import Live

PID = Path(os.getenv("XDG_RUNTIME_DIR") or "/tmp") / "wvcr-live.pid"


def read_pid() -> int | None:
    try:
        pid = int(PID.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError):
        PID.unlink(missing_ok=True)
        return None


def stop() -> int:
    pid = read_pid()
    if pid is None:
        return 0
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if read_pid() is None:
            return 0
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)
    PID.unlink(missing_ok=True)
    return 0


def run(echo_gate: bool, think: bool) -> int:
    api_key = get_api_key("gemini")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        return 1
    PID.write_text(str(os.getpid()))
    try:
        asyncio.run(Live(api_key, echo_gate=echo_gate, think=think).run())
    except Exception as e:
        logger.exception(e)
        HyprlandNotificationManager.send_notification("Live", str(e)[:200], color="#e74c3c")
        return 1
    finally:
        PID.unlink(missing_ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="wvcr-live")
    parser.add_argument("cmd", nargs="?", default="toggle", choices=["toggle", "stop", "run"])
    parser.add_argument("--no-gate", action="store_true", help="keep mic open while the model speaks (headphones)")
    parser.add_argument("--think", action="store_true", help="extended-thinking model: smarter, ~3s slower per step")
    args = parser.parse_args()
    logger.add(OUTPUT / "logs" / "live.log", rotation="1 MB", retention=3)
    if args.cmd == "stop":
        return stop()
    if args.cmd == "toggle" and read_pid() is not None:
        return stop()
    return run(echo_gate=not args.no_gate, think=args.think)


if __name__ == "__main__":
    sys.exit(main())

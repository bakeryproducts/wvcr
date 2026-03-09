import os
import sys
import time
import signal
import subprocess

PID_FILE = "/tmp/wvcr.pid"
SOCKET_PATH = "/tmp/wvcr.sock"


def get_daemon_pid() -> int | None:
    """Get daemon PID if running."""
    if not os.path.exists(PID_FILE):
        return None

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        # Check if process exists
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file exists but process doesn't
        if os.path.exists(PID_FILE):
            os.unlink(PID_FILE)
        return None


def start_daemon():
    """Start the daemon in background."""
    if get_daemon_pid():
        print("Daemon is already running")
        return

    print("Starting WVCR daemon...")

    # Start daemon as subprocess (detached)
    # Redirect stderr to log file for debugging subprocess issues
    log_dir = os.path.expanduser("~/Documents/wvcr/output/logs")
    os.makedirs(log_dir, exist_ok=True)
    stderr_log = open(os.path.join(log_dir, "daemon_stderr.log"), "a")

    subprocess.Popen(
        [sys.executable, "-m", "wvcr.daemon.server"],
        stdout=subprocess.DEVNULL,
        stderr=stderr_log,
        start_new_session=True,
    )

    # Wait for daemon to load heavy imports (can take 1-2s)
    print("Waiting for daemon to load imports...")
    for i in range(30):  # Wait up to 3 seconds
        time.sleep(0.1)
        if get_daemon_pid() and os.path.exists(SOCKET_PATH):
            print("Daemon started successfully")
            return

    print("Failed to start daemon", file=sys.stderr)
    sys.exit(1)


def stop_daemon():
    """Stop the daemon."""
    pid = get_daemon_pid()
    if not pid:
        print("Daemon is not running")
        return

    print(f"Stopping daemon (PID {pid})...")

    try:
        # Send SIGTERM
        os.kill(pid, signal.SIGTERM)

        # Wait for it to exit
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print("Daemon stopped")
                return

        # Force kill if still alive
        print("Daemon not responding, force killing...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        print("Daemon killed")

    except ProcessLookupError:
        print("Daemon already stopped")
    except PermissionError:
        print("Permission denied", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up
        if os.path.exists(PID_FILE):
            os.unlink(PID_FILE)
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)


def status_daemon():
    """Check daemon status."""
    pid = get_daemon_pid()
    if pid:
        print(f"Daemon is running (PID {pid})")
        print(f"Socket: {SOCKET_PATH}")
        return 0
    else:
        print("Daemon is not running")
        return 1


def main():
    """Entry point for daemon control."""
    import argparse

    parser = argparse.ArgumentParser(description="WVCR Daemon Control")
    parser.add_argument(
        "action",
        choices=["start", "stop", "restart", "status"],
        help="Daemon action",
    )

    args = parser.parse_args()

    if args.action == "start":
        start_daemon()
    elif args.action == "stop":
        stop_daemon()
    elif args.action == "restart":
        stop_daemon()
        time.sleep(0.5)
        start_daemon()
    elif args.action == "status":
        sys.exit(status_daemon())


if __name__ == "__main__":
    main()

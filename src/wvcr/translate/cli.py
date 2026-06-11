from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

from wvcr.config.env import get_api_key
from wvcr.notification_manager import SystemNotificationManager

from .audio import loopback_running, remap_source_exists, setup, sink_exists, teardown
from .picker import pick_preset
from .presets import Preset, load_presets, write_default_config
from .runner import run_translation


def pid_path() -> Path:
    runtime_dir = os.getenv("XDG_RUNTIME_DIR") or "/tmp"
    return Path(runtime_dir) / "wvcr-translate.pid"


def read_pid() -> int | None:
    p = pid_path()
    if not p.exists():
        return None
    try:
        pid = int(p.read_text().strip())
    except ValueError:
        return None
    if not _process_alive(pid):
        p.unlink(missing_ok=True)
        return None
    return pid


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_pid() -> None:
    pid_path().write_text(str(os.getpid()))


def clear_pid() -> None:
    pid_path().unlink(missing_ok=True)


def cmd_setup(args: argparse.Namespace) -> int:
    setup()
    write_default_config()
    logger.info("setup complete")
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    teardown()
    logger.info("teardown complete")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print(f"sink {'exists' if sink_exists() else 'missing'}")
    print(f"mic source {'exists' if remap_source_exists() else 'missing'}")
    print(f"loopback {'running' if loopback_running() else 'stopped'}")
    pid = read_pid()
    if pid:
        print(f"translating (pid={pid})")
    else:
        print("idle")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    pid = read_pid()
    if pid is None:
        print("not running")
        return 0
    print(f"stopping pid={pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        clear_pid()
        return 0
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            clear_pid()
            return 0
        time.sleep(0.1)
    logger.warning("process did not exit, sending SIGKILL")
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    clear_pid()
    return 0


def cmd_toggle(args: argparse.Namespace) -> int:
    pid = read_pid()
    if pid is not None:
        return cmd_stop(args)

    if not sink_exists():
        logger.info("sink missing, running setup first")
        setup()

    presets = load_presets()
    if args.language:
        match = next((p for p in presets if p.language == args.language), None)
        if match is None:
            match = Preset(name=args.language, language=args.language)
        preset = match
    else:
        preset = pick_preset(presets)
        if preset is None:
            logger.info("no preset chosen, exiting")
            return 0

    api_key = get_api_key("openai")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return 1

    write_pid()
    SystemNotificationManager.send_notification(
        title="Translate ON",
        text=f"-> {preset.name} ({preset.language})",
        timeout=2,
    )
    try:
        run_translation(preset, api_key, record=args.record)
    finally:
        clear_pid()
        SystemNotificationManager.send_notification(
            title="Translate OFF",
            text="restored mic",
            timeout=2,
        )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    presets = load_presets()
    if args.language:
        match = next((p for p in presets if p.language == args.language), None)
        preset = match or Preset(name=args.language, language=args.language)
    else:
        preset = pick_preset(presets)
        if preset is None:
            return 0
    api_key = get_api_key("openai")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return 1
    run_translation(preset, api_key, record=args.record)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wvcr-translate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="create virtual mic + loopback")
    sub.add_parser("teardown", help="remove virtual mic")
    sub.add_parser("status", help="show state")
    sub.add_parser("stop", help="stop active translation")

    p_toggle = sub.add_parser("toggle", help="toggle translation on/off")
    p_toggle.add_argument("-l", "--language", help="skip wofi, use language code")
    p_toggle.add_argument(
        "-r", "--record", action="store_true", help="save WAV + transcripts to output/translate"
    )

    p_run = sub.add_parser("run", help="run translation in foreground (no pidfile)")
    p_run.add_argument("-l", "--language", help="skip wofi, use language code")
    p_run.add_argument(
        "-r", "--record", action="store_true", help="save WAV + transcripts to output/translate"
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "setup": cmd_setup,
        "teardown": cmd_teardown,
        "status": cmd_status,
        "stop": cmd_stop,
        "toggle": cmd_toggle,
        "run": cmd_run,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

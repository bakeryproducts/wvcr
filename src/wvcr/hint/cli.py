from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from wvcr.config.env import get_api_key

from .audio import loopbacks_running, setup, sink_exists, teardown
from .runner import run_hint


def _load_context(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if path.is_file():
        return path.read_text()
    return value


def cmd_setup(args: argparse.Namespace) -> int:
    setup()
    logger.info("hint setup complete")
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    teardown()
    logger.info("hint teardown complete")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print(f"bus {'exists' if sink_exists() else 'missing'}")
    print(f"loopbacks {'running' if loopbacks_running() else 'stopped'}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    api_key = get_api_key("gemini")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        return 1
    context = _load_context(args.context)
    run_hint(api_key, hotkey=args.hotkey, window_seconds=args.window, context=context)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wvcr-hint")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="create hint bus + loopbacks")
    sub.add_parser("teardown", help="remove hint bus")
    sub.add_parser("status", help="show state")

    p_run = sub.add_parser("run", help="run hint listener in foreground")
    p_run.add_argument(
        "--hotkey", default="bookmarks", help="evdev key name to trigger a hint (default bookmarks)"
    )
    p_run.add_argument(
        "--window", type=float, default=600.0, help="seconds of audio to keep (default 600 = 10 min)"
    )
    p_run.add_argument(
        "--context",
        default=None,
        help="extra context appended to every prompt: a literal string, or a path to a text/md file",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "setup": cmd_setup,
        "teardown": cmd_teardown,
        "status": cmd_status,
        "run": cmd_run,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

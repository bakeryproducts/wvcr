import socket
import json
import sys
import argparse

from wvcr.commands import get_user_command_names, Command, COMMAND_REGISTRY

SOCKET_PATH = "/tmp/wvcr.sock"


def send_command(command: str, args: dict = None) -> dict:
    """Send command to daemon and get response."""
    if args is None:
        args = {}

    request = {"command": command, "args": args}

    try:
        # Connect to daemon
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)

        # Send request
        sock.sendall(json.dumps(request).encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        # Receive response
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk

        sock.close()

        response = json.loads(data.decode("utf-8"))
        return response

    except FileNotFoundError:
        print("Error: Daemon not running. Start it with: wvcr-daemon", file=sys.stderr)
        sys.exit(1)
    except ConnectionRefusedError:
        print("Error: Cannot connect to daemon", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for client."""
    parser = argparse.ArgumentParser(description="WVCR - Voice Recording Client")
    parser.add_argument(
        "command",
        choices=get_user_command_names(),
        help="Command to execute",
    )
    parser.add_argument("--url", help="URL for transcribe-url command")
    parser.add_argument("--instruction", help="Text instruction for explain/research")
    parser.add_argument(
        "--session-id", dest="session_id", help="Session ID for agentic mode"
    )
    parser.add_argument(
        "--app-name",
        dest="app_name",
        help="App name for agentic mode (default: ADK_APP_NAME env)",
    )
    parser.add_argument("--files", help="Comma-separated file paths for agentic mode")
    parser.add_argument(
        "--backend",
        choices=["adk", "gemini"],
        help="Agentic backend: 'adk' (external ADK API server) or 'gemini' (direct Gemini)",
    )
    parser.add_argument("--language", default="ru", help="Language code (default: ru)")
    parser.add_argument("--provider", help="Provider (openai/gemini)")
    parser.add_argument(
        "--vad", action="store_true", help="Enable voice activity detection"
    )
    parser.add_argument(
        "--citations",
        action="store_true",
        help="Append grounding source links to agentic (gemini) output",
    )

    args = parser.parse_args()

    # Build command arguments dynamically based on command spec
    cmd_args = {}
    cmd_enum = Command(args.command)
    spec = COMMAND_REGISTRY[cmd_enum]

    # Map CLI args to command args
    for arg_name in spec.args:
        if hasattr(args, arg_name) and getattr(args, arg_name) is not None:
            cmd_args[arg_name] = getattr(args, arg_name)

    # Send to daemon
    response = send_command(args.command, cmd_args)

    # Handle response
    if response["status"] == "success":
        result = response.get("result")
        if result:
            print(result)
        sys.exit(0)
    else:
        error = response.get("error", "Unknown error")
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

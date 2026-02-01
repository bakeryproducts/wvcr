import os
import socket
import json
import logging
from typing import Any

# Heavy imports - loaded once at daemon startup
from wvcr.cli.runtime import build_runtime_context
from wvcr.commands import Command, COMMAND_REGISTRY
from wvcr.modes2.transcribe_pipeline_mode import TranscribePipelineMode
from wvcr.modes2.transcribe_url_pipeline_mode import TranscribeUrlPipelineMode
from wvcr.modes2.explain_pipeline_mode import ExplainPipelineMode
from wvcr.modes2.voiceover_pipeline_mode import VoiceoverPipelineMode
from wvcr.modes2.research_pipeline_mode import ResearchPipelineMode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SOCKET_PATH = "/tmp/wvcr.sock"
PID_FILE = "/tmp/wvcr.pid"

# Pipeline mode class mapping
MODE_CLASSES = {
    "TranscribePipelineMode": TranscribePipelineMode,
    "TranscribeUrlPipelineMode": TranscribeUrlPipelineMode,
    "ExplainPipelineMode": ExplainPipelineMode,
    "VoiceoverPipelineMode": VoiceoverPipelineMode,
    "ResearchPipelineMode": ResearchPipelineMode,
}


class WVCRDaemon:
    def __init__(self):
        self.socket_path = SOCKET_PATH
        self.sock = None
        self.running = False
        logger.info("Initializing WVCR daemon with heavy imports...")
        # Pre-load runtime context (this is the slow part) - no config needed for daemon init
        self.runtime_ctx = build_runtime_context()  # Uses default config
        logger.info("Heavy imports loaded, daemon ready")

    def start(self):
        """Start the daemon socket server."""
        # Remove existing socket if present
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        # Write PID file
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))

        # Create Unix domain socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.socket_path)
        self.sock.listen(5)
        os.chmod(self.socket_path, 0o600)  # Only owner can connect

        logger.info(f"Daemon listening on {self.socket_path}")
        self.running = True

        try:
            while self.running:
                conn, _ = self.sock.accept()
                self._handle_client(conn)
        except KeyboardInterrupt:
            logger.info("Daemon interrupted, shutting down...")
        finally:
            self.cleanup()

    def _handle_client(self, conn: socket.socket):
        """Handle a single client connection."""
        try:
            # Receive command (max 64KB should be enough)
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if len(data) > 65536:  # Prevent memory abuse
                    raise ValueError("Message too large")

            if not data:
                return

            # Parse JSON command
            request = json.loads(data.decode("utf-8"))
            command = request.get("command")
            args = request.get("args", {})

            logger.info(f"Received command: {command}")

            # Execute command
            result = self._execute_command(command, args)

            # Send response
            response = {"status": "success", "result": result}
            conn.sendall(json.dumps(response).encode("utf-8"))

        except Exception as e:
            logger.error(f"Error handling client: {e}", exc_info=True)
            error_response = {"status": "error", "error": str(e)}
            try:
                conn.sendall(json.dumps(error_response).encode("utf-8"))
            except:
                pass
        finally:
            conn.close()

    def _execute_command(self, command: str, args: dict) -> Any:
        """Execute command using registry."""
        # Convert string to Command enum
        try:
            cmd = Command(command)
        except ValueError:
            raise ValueError(f"Unknown command: {command}")

        # Get command spec
        spec = COMMAND_REGISTRY.get(cmd)
        if not spec:
            raise ValueError(f"Command not in registry: {command}")

        # Handle special daemon commands
        if cmd == Command.PING:
            return "pong"
        
        if cmd == Command.SHUTDOWN:
            logger.info("Shutdown command received")
            self.running = False
            return "shutting down"

        # Handle pipeline commands
        if not spec.pipeline_mode:
            raise ValueError(f"Command {command} has no pipeline mode")

        # Update runtime context with args
        for arg_name, arg_value in args.items():
            if arg_value is not None:
                self.runtime_ctx.options[arg_name] = arg_value

        # Get and instantiate pipeline class
        mode_class = MODE_CLASSES[spec.pipeline_mode]
        pipeline = mode_class(self.runtime_ctx)
        state = pipeline.run()

        # Extract result based on command type
        result_key_map = {
            Command.TRANSCRIBE: "transcript",
            Command.TRANSCRIBE_URL: "transcript",
            Command.EXPLAIN: "explanation",
            Command.VOICEOVER: "voiceover_file",
            Command.RESEARCH: "research_result",
        }
        
        result_key = result_key_map.get(cmd, "result")
        return state.get(result_key, "")

    def cleanup(self):
        """Clean up resources."""
        if self.sock:
            self.sock.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        if os.path.exists(PID_FILE):
            os.unlink(PID_FILE)
        logger.info("Daemon cleaned up")


def main():
    """Main entry point for daemon."""
    daemon = WVCRDaemon()
    daemon.start()


if __name__ == "__main__":
    main()

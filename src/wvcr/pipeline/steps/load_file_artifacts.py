import base64
import mimetypes
from pathlib import Path

from loguru import logger

from ..step import Step, StepError


class LoadFileArtifacts(Step):
    name = "load_file_artifacts"
    provides = {"file_parts"}

    def execute(self, state, ctx):
        files_str = state.get("files", "")
        if not files_str:
            state.set("file_parts", [])
            return

        paths = [p.strip() for p in files_str.split(",") if p.strip()]
        if not paths:
            state.set("file_parts", [])
            return

        parts = []
        for path_str in paths:
            path = Path(path_str).expanduser()
            if not path.exists():
                raise StepError(f"File not found: {path}")

            mime_type, _ = mimetypes.guess_type(str(path))
            if not mime_type:
                mime_type = "application/octet-stream"

            data = path.read_bytes()
            b64_data = base64.b64encode(data).decode("utf-8")

            part = {
                "inlineData": {
                    "mimeType": mime_type,
                    "data": b64_data,
                }
            }
            parts.append(part)
            logger.debug(
                f"Loaded file artifact: {path} ({mime_type}, {len(data)} bytes)"
            )

        state.set("file_parts", parts)
        logger.info(f"Loaded {len(parts)} file artifacts")

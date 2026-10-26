import asyncio
import signal
import subprocess
import time
from pathlib import Path

from google import genai
from google.genai import types
from loguru import logger

from . import hypr

MODEL = "gemini-3.8-live"
IN_RATE = 16000
OUT_RATE = 24000
FRAME_BYTES = IN_RATE // 50 * 2
ECHO_TAIL = 0.3
OVERLAY = Path(__file__).with_name("overlay.py")

PROMPT = """You are a voice controller for the user's Hyprland desktop. You act through tools; you are not a chatbot.

Rules:
- Be extremely brief. Confirm with one or two words or say nothing. Never narrate what you are about to do.
- The user often pauses to think. If an utterance sounds unfinished, stay silent and wait.
- When asked to type, write or dictate text, pass it to type_text verbatim, in the language spoken, without rephrasing, translating or adding anything.
- type_text never presses Enter. Press keys only when asked.
- Target windows by address. Every tool result contains the fresh window list.
- To read what is on screen use look. The window must be on the visible workspace.
- To open apps or trigger the user's shortcuts use dispatch with the dispatcher and args from the bindings below.
- Speak the user's language (usually Russian).
- When the user says to stop, finish or bye, call stop without saying anything.

User key bindings (combo: dispatcher args):
{binds}

User habits (follow these over the bindings):
{notes}

Current windows:
{state}
"""
NOTES = Path.home() / ".config/wvcr/live.md"

ADDRESS = {"type": "string", "description": "Window address like 0x55..., defaults to the focused window"}
TOOLS = [{"function_declarations": [
    {"name": "workspace", "description": "Switch to a workspace.",
     "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}},
    {"name": "focus", "description": "Focus a window.",
     "parameters": {"type": "object", "properties": {"address": ADDRESS}, "required": ["address"]}},
    {"name": "type_text", "description": "Focus a window and insert text into it exactly as given. Does not press Enter.",
     "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "address": ADDRESS}, "required": ["text"]}},
    {"name": "press_keys", "description": "Send key combos to a window, space separated, e.g. 'enter', 'escape', 'ctrl+c', 'down down enter'.",
     "parameters": {"type": "object", "properties": {"keys": {"type": "string"}, "address": ADDRESS}, "required": ["keys"]}},
    {"name": "dispatch", "description": "Run a hyprctl dispatcher, e.g. exec with a command from the bindings, movetoworkspace, killactive, togglefloating, fullscreen.",
     "parameters": {"type": "object", "properties": {"dispatcher": {"type": "string"}, "arg": {"type": "string"}}, "required": ["dispatcher"]}},
    {"name": "look", "description": "Screenshot a window (default focused) or the whole screen with address 'screen'; the image arrives as the latest video frame.",
     "parameters": {"type": "object", "properties": {"address": ADDRESS}}},
    {"name": "stop", "description": "End this voice session."},
]}]


class Live:
    def __init__(self, api_key: str, echo_gate: bool = True):
        self.client = genai.Client(api_key=api_key)
        self.echo_gate = echo_gate
        self.session = None
        self.handle = None
        self.prompt = ""
        self.speaking_until = 0.0
        self.busy = False
        self.stopping = False
        self.ui = None
        self.ui_state = ""
        self.player = None
        self.heard = ""
        self.said = ""

    def config(self) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=self.prompt,
            tools=TOOLS,
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
            session_resumption=types.SessionResumptionConfig(handle=self.handle),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(silence_duration_ms=700)
            ),
        )

    def _spawn_player(self) -> subprocess.Popen:
        return subprocess.Popen(
            ["pacat", "--playback", f"--rate={OUT_RATE}", "--channels=1", "--format=s16le", "--raw", "--latency-msec=40"],
            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )

    def _play(self, pcm: bytes) -> None:
        now = time.monotonic()
        self.speaking_until = max(now, self.speaking_until) + len(pcm) / (OUT_RATE * 2)
        try:
            self.player.stdin.write(pcm)
        except (BrokenPipeError, ValueError):
            pass

    def _flush_player(self) -> None:
        self.player.kill()
        self.player = self._spawn_player()
        self.speaking_until = 0.0

    def _set_ui(self, st: str) -> None:
        if st == self.ui_state or self.ui is None:
            return
        self.ui_state = st
        try:
            self.ui.stdin.write(st + "\n")
            self.ui.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass

    async def _ui_loop(self) -> None:
        while True:
            if self.session is None:
                st = "connect"
            elif self.busy:
                st = "tool"
            elif time.monotonic() < self.speaking_until:
                st = "speak"
            else:
                st = "listen"
            self._set_ui(st)
            await asyncio.sleep(0.1)

    async def _mic_loop(self) -> None:
        proc = subprocess.Popen(
            ["pacat", "--record", "--device=@DEFAULT_SOURCE@", f"--rate={IN_RATE}", "--channels=1", "--format=s16le", "--raw", "--latency-msec=20"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )
        loop = asyncio.get_running_loop()
        silence = bytes(FRAME_BYTES)
        try:
            while True:
                chunk = await loop.run_in_executor(None, proc.stdout.read, FRAME_BYTES)
                if not chunk:
                    logger.warning("mic closed")
                    return
                if self.echo_gate and time.monotonic() < self.speaking_until + ECHO_TAIL:
                    chunk = silence[: len(chunk)]
                s = self.session
                if s is None:
                    continue
                try:
                    await s.send_realtime_input(audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={IN_RATE}"))
                except Exception as e:
                    logger.debug(f"send audio: {e}")
        finally:
            proc.kill()

    def _run_tool(self, name: str, a: dict):
        if name == "workspace":
            hypr.dispatch("workspace", str(a["n"]))
        elif name == "focus":
            hypr.dispatch("focuswindow", f"address:{a['address']}")
        elif name == "type_text":
            hypr.type_text(a["text"], a.get("address"))
        elif name == "press_keys":
            hypr.press(a["keys"], a.get("address"))
        elif name == "dispatch":
            if a["dispatcher"] == "exec":
                return hypr.exec_wait(a.get("arg", ""))
            hypr.dispatch(a["dispatcher"], a.get("arg", ""))
        elif name == "look":
            return hypr.screenshot(a.get("address"))
        elif name == "stop":
            self.stopping = True
            return "stopping"
        else:
            raise ValueError(f"unknown tool {name}")
        time.sleep(0.2)
        return "ok"

    async def _tools(self, s, tool_call) -> None:
        self.busy = True
        responses = []
        try:
            for fc in tool_call.function_calls:
                args = dict(fc.args or {})
                logger.info(f"tool {fc.name} {args}")
                try:
                    result = await asyncio.to_thread(self._run_tool, fc.name, args)
                    if isinstance(result, bytes):
                        await s.send_realtime_input(video=types.Blob(data=result, mime_type="image/jpeg"))
                        result = "screenshot sent as the latest video frame"
                    resp = {"result": result}
                except Exception as e:
                    logger.warning(f"tool {fc.name} failed: {e}")
                    resp = {"error": str(e)}
                if not self.stopping:
                    resp["windows"] = await asyncio.to_thread(hypr.state)
                responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response=resp))
            await s.send_tool_response(function_responses=responses)
        finally:
            self.busy = False
        if self.stopping:
            asyncio.get_running_loop().call_later(0.3, self._stop.set)

    async def _receive(self, s) -> None:
        while True:
            async for msg in s.receive():
                upd = msg.session_resumption_update
                if upd and upd.resumable and upd.new_handle:
                    self.handle = upd.new_handle
                if msg.go_away:
                    logger.info(f"go_away {msg.go_away.time_left}, reconnecting")
                    return
                if msg.tool_call:
                    await self._tools(s, msg.tool_call)
                sc = msg.server_content
                if not sc:
                    continue
                if sc.interrupted:
                    self._flush_player()
                if sc.input_transcription and sc.input_transcription.text:
                    self.heard += sc.input_transcription.text
                if sc.output_transcription and sc.output_transcription.text:
                    self.said += sc.output_transcription.text
                if sc.model_turn:
                    for part in sc.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            self._play(part.inline_data.data)
                if sc.turn_complete:
                    if self.heard.strip():
                        logger.info(f"user: {self.heard.strip()}")
                    if self.said.strip():
                        logger.info(f"model: {self.said.strip()}")
                    self.heard = self.said = ""

    async def run(self) -> None:
        self._stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._stop.set)
        self.ui = subprocess.Popen(
            ["/usr/bin/python3", str(OVERLAY)], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        self.player = self._spawn_player()
        self.prompt = PROMPT.format(
            binds=hypr.binds(),
            notes=NOTES.read_text().strip() if NOTES.exists() else "none",
            state=hypr.state(),
        )
        bg = [asyncio.create_task(self._mic_loop()), asyncio.create_task(self._ui_loop())]
        failures = 0
        try:
            while not self._stop.is_set():
                try:
                    async with self.client.aio.live.connect(model=MODEL, config=self.config()) as s:
                        logger.info(f"connected (resumed={self.handle is not None})")
                        self.session = s
                        failures = 0
                        recv = asyncio.create_task(self._receive(s))
                        stop = asyncio.create_task(self._stop.wait())
                        done, pending = await asyncio.wait({recv, stop}, return_when=asyncio.FIRST_COMPLETED)
                        for t in pending:
                            t.cancel()
                        if recv in done and recv.exception():
                            raise recv.exception()
                except Exception as e:
                    failures += 1
                    logger.warning(f"session error ({failures}): {e}")
                    if failures >= 3:
                        raise
                    await asyncio.sleep(1)
                finally:
                    self.session = None
        finally:
            for t in bg:
                t.cancel()
            for p in (self.player, self.ui):
                try:
                    p.stdin.close()
                except Exception:
                    pass
                p.terminate()

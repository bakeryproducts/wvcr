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
THINK_MODEL = "gemini-3.8-live-extended-thinking"
IN_RATE = 16000
OUT_RATE = 24000
FRAME_BYTES = IN_RATE // 50 * 2
OVERLAY = Path(__file__).with_name("overlay.py")

PROMPT = """**Persona:**
You are the user's hands-free computer assistant. The user is a developer working at their Linux desktop (Hyprland, mostly terminals). They talk to you while they work and you operate the computer for them: switch and arrange windows, type text and commands, press keys, open apps, and look at the screen to read, check and explain what is there. You are their hands and eyes on the desktop, and a sharp colleague they can ask about what they see.

RESPOND IN RUSSIAN. YOU MUST RESPOND UNMISTAKABLY IN RUSSIAN. The user speaks Russian mixed with English technical terms (git, commit, diff, Enter, Ctrl, workspace, terminal); hear unclear words as Russian or technical terms, never as other languages.

**Conversational loop:**
The session is an open loop that lasts as long as the user wants. On each request:
1. Work out what the user wants, using everything said and done earlier in the session. Resolve "that window", "back", "the previous one", "again" from the history.
2. If you need to know what is on screen to do it right, call look first.
3. Do it with tools. Multi-step requests are normal: do every step in order.
4. When you need the result to continue or to answer (command output, a menu that opened, an agent's reply), call look. Plain actions like switching, focusing or typing need no check.
5. Reply. After a plain action, confirm briefly. When the user asks a question or wants your opinion, answer it properly with the substance, not a filler. Do not announce plans before acting and do not repeat the user's words back.

**Desktop:**
The desktop state is below. A fresh one comes with every tool result and as a [desktop] message whenever focus, workspace or windows change; always trust the latest. Windows are referenced by address. "This window" or "here" is the focused window. Look for windows on the visible workspace first unless the user names another place. The largest window on a workspace is the main one. Terminals show their foreground program, e.g. "running opencode" or "running zsh".

**Tools:**
Use type_text to insert text into a window. It inserts exactly what you give and never presses Enter. Dictated text goes in verbatim, in the spoken language; when the user asks you to compose a command or message, write it yourself.
Use press_keys to send keys into an application, e.g. Enter, Escape, arrows, app shortcuts.
Use dispatch for anything bound to a Hyprland shortcut in the bindings below, with that binding's dispatcher and args. Hyprland shortcuts do not work through press_keys.
Use look to get a screenshot of a window or the screen. Before moving through menus or lists with arrow keys, look to see where the cursor is and count the steps.
When the user says stop, finish or bye, call stop without speaking.

**Guardrails:**
Describe only what you actually see in a screenshot. If it is unreadable or you did not look, say so; never guess screen contents.
If a request is ambiguous and a wrong guess is costly (closing, sending, committing, deleting), ask a short question first.
The user often pauses mid-sentence. If an utterance sounds unfinished, wait.
If an action did not work, say so and try another way instead of repeating the same call.

User key bindings (combo: dispatcher args):
{binds}

User habits (follow these over the bindings):
{notes}

Desktop at session start:
{state}
"""
NOTES = Path.home() / ".config/wvcr/live.md"
VOCAB = ["git", "commit", "push", "diff", "Enter", "Escape", "Ctrl", "Alt", "Super", "Shift", "Tab", "workspace", "terminal", "OpenCode", "Hyprland", "lf"]

ADDRESS = {"type": "string", "description": "Window address like 0x55..., defaults to the focused window"}
FUNCTIONS = [
    {"name": "workspace", "description": "Switch to a workspace.",
     "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}},
    {"name": "focus", "description": "Focus a window, switching to its workspace if needed.",
     "parameters": {"type": "object", "properties": {"address": ADDRESS}, "required": ["address"]}},
    {"name": "type_text", "description": "Focus a window and insert text into it exactly as given. Does not press Enter.",
     "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "address": ADDRESS}, "required": ["text"]}},
    {"name": "press_keys", "description": "Focus a window and send key combos into the application, space separated, e.g. 'enter', 'escape', 'ctrl+c', 'ctrl+x k', 'down down enter'. Not for Hyprland shortcuts.",
     "parameters": {"type": "object", "properties": {"keys": {"type": "string"}, "address": ADDRESS}, "required": ["keys"]}},
    {"name": "dispatch", "description": "Run a hyprctl dispatcher: exec with a command from the bindings, layoutmsg, movetoworkspace, killactive, togglefloating, fullscreen, etc. Use this for anything bound to a Hyprland shortcut.",
     "parameters": {"type": "object", "properties": {"dispatcher": {"type": "string"}, "arg": {"type": "string"}}, "required": ["dispatcher"]}},
    {"name": "look", "description": "Screenshot a window (default focused) or the whole visible screen with address 'screen'. The image is attached to the result.",
     "parameters": {"type": "object", "properties": {"address": ADDRESS}}},
    {"name": "stop", "description": "End this voice session."},
]


class Live:
    def __init__(self, api_key: str, echo_gate: bool = True, think: bool = False):
        self.client = genai.Client(api_key=api_key)
        self.echo_gate = echo_gate
        self.think = think
        self.model = THINK_MODEL if think else MODEL
        self.session = None
        self.handle = None
        self.prompt = ""
        self.speaking_until = 0.0
        self.busy = False
        self.thinking = False
        self.stopping = False
        self.ui = None
        self.ui_state = ""
        self.player = None
        self.heard = ""
        self.said = ""
        self.desk = None

    def config(self) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=self.prompt,
            tools=[{"function_declarations": [{**fn, "behavior": "NON_BLOCKING"} for fn in FUNCTIONS] if self.think else FUNCTIONS}],
            thinking_config=types.ThinkingConfig(thinking_level="medium") if self.think else None,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
            input_audio_transcription=types.AudioTranscriptionConfig(language_codes=["ru-RU", "en-US"], custom_vocabulary=VOCAB),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
            session_resumption=types.SessionResumptionConfig(handle=self.handle),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(silence_duration_ms=1000)
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
            elif self.thinking:
                st = "think"
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
                if self.echo_gate and time.monotonic() < self.speaking_until:
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
                parts = None
                try:
                    result = await asyncio.to_thread(self._run_tool, fc.name, args)
                    if isinstance(result, bytes):
                        parts = [types.FunctionResponsePart(inline_data=types.FunctionResponseBlob(mime_type="image/jpeg", data=result))]
                        result = "screenshot attached"
                    resp = {"result": result}
                except Exception as e:
                    logger.warning(f"tool {fc.name} failed: {e}")
                    resp = {"error": str(e)}
                if not self.stopping:
                    resp["desktop"] = await asyncio.to_thread(hypr.state)
                responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response=resp, parts=parts))
            await s.send_tool_response(function_responses=responses)
            self.desk = await asyncio.to_thread(hypr.layout_key)
        finally:
            self.busy = False
        if self.stopping:
            asyncio.get_running_loop().call_later(0.3, self._stop.set)

    async def _desk_loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            s = self.session
            if s is None or self.busy or self.stopping:
                continue
            try:
                key = await asyncio.to_thread(hypr.layout_key)
                if key == self.desk:
                    continue
                self.desk = key
                st = await asyncio.to_thread(hypr.state)
                await s.send_client_content(turns=[{"role": "user", "parts": [{"text": f"[desktop]\n{st}"}]}], turn_complete=False)
                logger.debug(f"desktop pushed: ws {key[0]} focus {key[1]}")
            except Exception as e:
                logger.debug(f"desktop push: {e}")

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
                if sc.interaction_status:
                    self.thinking = sc.interaction_status == types.InteractionStatus.IN_PROGRESS
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
        logger.debug(f"system prompt:\n{self.prompt}")
        self.desk = hypr.layout_key()
        bg = [asyncio.create_task(t) for t in (self._mic_loop(), self._ui_loop(), self._desk_loop())]
        failures = 0
        try:
            while not self._stop.is_set():
                try:
                    async with self.client.aio.live.connect(model=self.model, config=self.config()) as s:
                        logger.info(f"connected {self.model} (resumed={self.handle is not None})")
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

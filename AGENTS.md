# WVCR Architecture Overview

WVCR is a Linux-first voice recording toolkit that can run agents:
- Capturing microphone audio with VAD-driven stop/start behavior.
- Invoking LLM providers / ADK agents for various tasks

**Daemon Architecture**: See [docs/DAEMON.md](docs/DAEMON.md) for the client-daemon model, unified command registry, and auto-start behavior.

## Repository Layout

```
wvcr/
├── README.md
├── docs/
│   └── DAEMON.md
├── src/
│   └── wvcr/
│       ├── commands.py    # Unified command registry
│       ├── cli/           # Client, config, entrypoints
│       ├── daemon/        # Server, control, lifecycle
│       ├── ipc/           # Unix-socket audio transport
│       ├── modes2/        # Pipeline mode definitions
│       ├── pipeline/      # Generic pipeline engine & steps
│       ├── services/      # Transcription, download, clipboard
│       ├── adk/           # Google ADK research agents
│       └── voiceover.py
└── output/                # Timestamped transcripts, research, voiceover
```

## Pipelines
- **Implemented pipelines** – `transcribe`, `transcribe-url`, `explain`, `voiceover`, `research`, and `agentic` (see `src/wvcr/modes2`)

## Runtime Context & Pipeline Engine
- `build_runtime_context` (`src/wvcr/cli/runtime.py`) hydrates a `RuntimeContext` (`src/wvcr/pipeline/context.py`) with OpenAI/Gemini configs, recorder/player options, notifier, and service singletons (notably `IPCVoiceRecorder`).
- The generic pipeline runner (`src/wvcr/pipeline/pipeline.py`) executes ordered `Step` classes (`src/wvcr/pipeline/step.py`) against a mutable `WorkingState` (`src/wvcr/pipeline/state.py`), honoring `requires`/`provides`, timing metrics, and `StepError` recovery.

## Pipeline Definitions (`src/wvcr/modes2`)
- **TranscribePipelineMode** – Initializes run metadata, prepares an output path, configures + records audio, transcribes, saves to `output/transcribe`, copies text to clipboard, and publishes notifications.
- **TranscribeUrlPipelineMode** – Fetches a URL from config/clipboard, downloads audio via `DownloadAudioStep`, then reuses transcription, save, clipboard, and notification steps.
- **ExplainPipelineMode** – Optionally injects a prerecorded instruction; otherwise records/transcribes like the transcribe pipeline, ingests extra “thing” context (clipboard text or Wayland image), calls `ExplainTextStep`, and saves/announces the explanation.
- **VoiceoverPipelineMode** – Reads text from clipboard, generates speech via OpenAI TTS, and saves to `output/voiceover`.
- **ResearchPipelineMode** – Accepts text instruction or audio input; routes to local ADK agent (`src/wvcr/adk/runner.py`) with in-memory session.
- **AgenticPipelineMode** – Records audio, optionally accepts `--instruction`, `--files`, `--app-name`, `--session-id`, `--backend`. Selectable backend (`--backend`, default `gemini`): `gemini` calls Gemini directly via `RunAgenticGeminiStep` (single-shot, no ADK tools); `adk` calls the external ADK API Server via `RunAgenticStep`, auto-creating a session if needed. Saves to `output/agentic`.

## Step Inventory (`src/wvcr/pipeline/steps`)
- **Bootstrapping** – `InitState`, `PrepareOutputPath`, and `SetKeyFromArg` seed state; `PasteFromClipboard` supports text or Wayland images.
- **Lifecycle** (`lifecycle_steps.py`) – `InitState`, `PrepareOutputPath`, `SetKeyFromArg`, `Finalize` handle pipeline initialization and cleanup.
- **I/O** (`io_steps.py`) – `PasteFromClipboard` (text/Wayland images), `CopyToClipboard`, `SaveTranscript`, `SaveExplanation`, `SaveResearchResult`, `SaveAgenticResult`.
- **Recording** – `ConfigureRecording` merges defaults/CLI overrides, `RecordAudio` calls the IPC recorder, `DownloadAudioStep` handles yt-dlp/ffmpeg extraction.
- **AI calls** – `TranscribeAudioStep` selects OpenAI vs Gemini via `ctx.get_stt_config()`. `ExplainTextStep` delegates to the text-processing service. `RunResearchAgentStep` invokes ADK. `RunAgenticStep` (external ADK API) and `RunAgenticGeminiStep` (direct Gemini) are the swappable agentic backends.
- **Notifications** – `Notify`, `NotifyTranscription`

## Google ADK Integration (`src/wvcr/adk`)
- `runner.py` wraps async ADK execution via `run_research()`
- `coordinator.py` defines the root agent that delegates to specialized agents.

## Audio & IPC Stack
- `IPCVoiceRecorder` (`src/wvcr/ipc/ipc_recorder.py`) captures microphone audio through `IPCMicHandler`, which spins up a Unix-domain socket server (`UnixAudioInput`) plus a forked `_capture_worker` (both in `src/wvcr/ipc/audio_ipc.py`). The worker streams VAD-filtered PCM frames (Silero-based by default in `src/wvcr/services/vad.py`).
- Audio format (WAV/MP3) is controlled via `RecorderAudioConfig.AUDIO_FORMAT` (defaults to MP3 @ 16 kbps to match Gemini downsampling). MP3 encoding pipes raw PCM directly to ffmpeg stdin without temp files. Format flows from config → `ctx.options["format"]` → `PrepareOutputPath` (sets file extension) → `ConfigureRecording` → `RecordAudio`.
- Keyboard stop monitoring lives in `src/wvcr/common.py` (pynput by default; optional evdev for Wayland). Playback utilities include `SpeechPlayer` (`src/wvcr/player.py`) and low-latency streaming components in `src/wvcr/standalone/audio_player.py`.
- Voiceover flows (`src/wvcr/voiceover.py` + `src/wvcr/test_audio.py`) read clipboard text, request OpenAI TTS audio, and optionally play or store WAV output under `output/voiceover`.

## Service Layer (`src/wvcr/services`)
- `transcription_service.py` abstracts Whisper vs Gemini STT, including MIME-aware uploads and temperature control.
- `text_processing_service.py` implements answer/explain prompts, reusing recent transcripts/answers via `Messages` (`src/wvcr/messages.py`).
- `download_service.py` retrieves remote audio (URL or YouTube) and re-encodes via ffmpeg. `file_service.py` centralizes timestamped naming for transcripts, recordings, downloads, and voiceovers.
- `notification_manager.py` wraps Plyer system notifications; `clipboard.py` adds Wayland-friendly image extraction.


## Operational Notes
- `.env` loading and API configuration happen in `src/wvcr/config.py`; missing keys will raise runtime errors before any AI calls.
- Outputs are timestamped per mode under `output/<mode>/`, enabling downstream steps (answer/explain) to build history chains quickly.
- Keyboard monitors honor the `WVCR_USE_EVDEV` env var for Wayland reliability

## Live Translate (`src/wvcr/translate`)
- Independent PulseAudio-based pipeline (`wvcr-translate` entrypoint), separate from the daemon/pipeline stack.
- `audio.py` builds a virtual mic: `module-null-sink` (`wvcr-virtmic`) + loopback from the real mic + `module-remap-source` exposing it as "WVCR Mic" for apps (Zoom etc.).
- `runner.py` stops that loopback while translating, streams the real mic via `pacat` into a Gemini/OpenAI realtime session, and plays translated audio back into `wvcr-virtmic` so calling apps hear the translation instead of raw speech.

## Live Hints (`src/wvcr/hint`)
- Independent, Cluely-style "press a key, get a popup hint" pipeline (`wvcr-hint` entrypoint). Does not touch or conflict with `translate` — uses its own PulseAudio bus.
- `audio.py` creates `wvcr-hintbus` (null-sink) with two loopbacks into it: default source (mic) and default sink's monitor (whatever plays in headphones/speakers), mixed natively by PulseAudio. `@DEFAULT_MONITOR@` is unreliable under PipeWire's pulse-compat (resolves to the mic), so device names are resolved explicitly. `reconcile()` is idempotent and self-healing (drops stale/duplicate loopbacks, repoints to current defaults); a `pactl subscribe` watcher thread calls it live whenever the default sink/source changes (e.g. switching to Bluetooth/HDMI), so capture always follows what you actually hear. The watcher is joined before `teardown()` to avoid resurrecting the bus on shutdown.
- `buffer.py`'s `RingBuffer` reads raw PCM16 from `pacat --record wvcr-hintbus.monitor` in a background thread into an in-memory rolling window (default 600s). Idle CPU cost is ~0 (blocking I/O). On demand, compresses the snapshot to MP3 @16kbps via in-memory ffmpeg pipe (matches Gemini's internal 16kbps downsampling, so no quality is lost by compressing first — cuts payload ~16x vs raw PCM/WAV).
- `hotkey.py` provides a global hotkey: evdev backend on Wayland (reads real keyboard devices directly, works when compositor doesn't support global shortcuts), pynput fallback on X11. Note: laptop F-row keys often don't emit standard F-codes without Fn/Fn-Lock (EC/firmware level, unfixable in software) — pick a key confirmed via `evtest`. Avoid keys with OS/app-level bindings (e.g. `bookmarks` opens a Firefox tab, handled natively below the shortcut layer — not disableable via about:config); unbound keys like `F13`/`F14`/`F15` are confirmed present across keyboards and safe.
- On hotkey press, `runner.py` first shows `picker.py` (a gtk-layer-shell selector, centered, big emoji + caption per row, navigable with arrows or j/k, Enter/Escape) to pick a **mode**, then takes a buffer snapshot and calls the LLM with that mode's prompt. Modes (`llm.py` `PROMPTS`/`MODE_META`):
  - **hint** — useful fact/risk/next-step about the current topic (original default behavior).
  - **gps** — given a goal (via `--context`), judge drift and steer back / give the next step.
  - **bestmove** — infer the implicit objective and suggest the single best next thing to say.
  - **explain** — rewrite my just-given bad explanation as a clear numbered breakdown/analogy.
  - **spravochnik** — wiki-style reference on the last term/fact mentioned.
  - **question** — one sharp clarifying question to ask the other participant.
- `--context` (CLI flag, string or path to a text/md file) is concatenated into every prompt regardless of mode — e.g. a stated goal for `gps`, or background docs.
- `WVCR_HINT_DEBUG_AUDIO=1` dumps the exact MP3 bytes sent to Gemini to `/tmp/wvcr-hint-<mode>-<ts>.mp3`, for verifying capture.
- `llm.py` sends the MP3 + mode prompt to `gemini-3.5-flash` with Google Search grounding enabled (`types.Tool(google_search=...)`), forcing plain-text Russian output. Prompt is anchored on the last moment of audio (not earlier topics) and always surfaces useful info even without an explicit question.
- `runner.py` wires hotkey → mode picker → buffer snapshot → LLM call (own thread, non-blocking, drops overlapping presses) → `LayerShellNotificationManager` popup.
- `popup.py` renders the actual hint: a custom `gtk-layer-shell` window (GTK3 + `GtkLayerShell`, anchored `BOTTOM` only so the compositor centers it horizontally), run as a **detached subprocess via system `/usr/bin/python3`** (not the project venv — avoids needing PyGObject in the conda/venv env). Chosen over dunst/mako because notification daemons only allow global positioning/width, not per-app overrides (confirmed via `man dunst.5`); a bespoke layer-shell surface is the standard workaround (see e.g. WayNotify). No text truncation (label wraps, no fixed height), manual close only (click card, click ×, or Escape — no auto-timeout on the actual hint text; short-lived status messages like "thinking..." still auto-dismiss). A pidfile at `/tmp/wvcr-hint-popup.pid` kills any previous popup before showing a new one so they don't stack. `notification_manager.py`'s `LayerShellNotificationManager` wraps `show_popup()` behind the same `NotificationBackend` protocol as `SystemNotificationManager`/`HyprlandNotificationManager`.


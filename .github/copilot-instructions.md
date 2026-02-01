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
- **Implemented pipelines** – `transcribe`, `transcribe-url`, `explain`, `voiceover`, and `research` (see `src/wvcr/modes2`)

## Runtime Context & Pipeline Engine
- `build_runtime_context` (`src/wvcr/cli/runtime.py`) hydrates a `RuntimeContext` (`src/wvcr/pipeline/context.py`) with OpenAI/Gemini configs, recorder/player options, notifier, and service singletons (notably `IPCVoiceRecorder`).
- The generic pipeline runner (`src/wvcr/pipeline/pipeline.py`) executes ordered `Step` classes (`src/wvcr/pipeline/step.py`) against a mutable `WorkingState` (`src/wvcr/pipeline/state.py`), honoring `requires`/`provides`, timing metrics, and `StepError` recovery.

## Pipeline Definitions (`src/wvcr/modes2`)
- **TranscribePipelineMode** – Initializes run metadata, prepares an output path, configures + records audio, transcribes, saves to `output/transcribe`, copies text to clipboard, and publishes notifications.
- **TranscribeUrlPipelineMode** – Fetches a URL from config/clipboard, downloads audio via `DownloadAudioStep`, then reuses transcription, save, clipboard, and notification steps.
- **ExplainPipelineMode** – Optionally injects a prerecorded instruction; otherwise records/transcribes like the transcribe pipeline, ingests extra “thing” context (clipboard text or Wayland image), calls `ExplainTextStep`, and saves/announces the explanation.
- **VoiceoverPipelineMode** – Reads text from clipboard, generates speech via OpenAI TTS, and saves to `output/voiceover`.
- **ResearchPipelineMode** – Accepts text instruction or audio input; routes to ADK agent (`src/wvcr/adk/runner.py`), which orchestrates agents for multi-step research

## Step Inventory (`src/wvcr/pipeline/steps`)
- **Bootstrapping** – `InitState`, `PrepareOutputPath`, and `SetKeyFromArg` seed state; `PasteFromClipboard` supports text or Wayland images.
- **Lifecycle** (`lifecycle_steps.py`) – `InitState`, `PrepareOutputPath`, `SetKeyFromArg`, `Finalize` handle pipeline initialization and cleanup.
- **I/O** (`io_steps.py`) – `PasteFromClipboard` (text/Wayland images), `CopyToClipboard`, `SaveTranscript`, `SaveExplanation`, `SaveResearchResult`.
- **Recording** – `ConfigureRecording` merges defaults/CLI overrides, `RecordAudio` calls the IPC recorder, `DownloadAudioStep` handles yt-dlp/ffmpeg extraction.
- **AI calls** – `TranscribeAudioStep` selects OpenAI vs Gemini via `ctx.get_stt_config()`. `ExplainTextStep` delegates to the text-processing service. `RunResearchAgentStep` invokes ADK.
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

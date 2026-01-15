# WVCR Architecture Overview

## Project Purpose
WVCR is a Linux-first voice recording and transcription toolkit that automates:
- Capturing microphone audio with VAD-driven stop/start behavior.
- Invoking OpenAI or Gemini speech/language models for transcription, QA, or explanation tasks.
- Distributing results through clipboard copies, desktop notifications, and persisted artifacts under `output/<mode>/`.

## Repository Layout
```
wvcr/
├── README.md
├── docs/
│   └── components.md   ← this document
├── src/
│   └── wvcr/
│       ├── cli/        # Hydra entrypoints & configs
│       ├── ipc/        # Unix-socket audio transport
│       ├── modes2/     # Pipeline mode definitions
│       ├── pipeline/   # Generic pipeline engine & steps
│       ├── services/   # Transcription, download, clipboard helpers
│       ├── standalone/ # Google ADK streaming client
│       ├── voiceover.py
│       └── ...
├── tests/               # Legacy pytest suites (require updates)
└── output/              # Timestamped transcripts, explanations, audio
```

## Entry Points & Modes
- **Hydra CLI (`src/wvcr/cli/main.py`)** – Registers typed configs from `src/wvcr/cli/config.py`, loads defaults from `cli/config.yaml`, and dispatches to pipeline runners under `src/wvcr/cli/pipelines` based on `pipeline=<mode>`.
- **Legacy script (`src/wvcr/main.py`)** – Still wiring against a removed `wvcr.modes` module; use the Hydra path instead.
- **Implemented pipelines** – `transcribe`, `transcribe-url`, and `explain` (see `src/wvcr/modes2`). `answer` and `voiceover` entries exist but forward to placeholders until those flows are ported.

## Runtime Context & Pipeline Engine
- `build_runtime_context` (`src/wvcr/cli/runtime.py`) hydrates a `RuntimeContext` (`src/wvcr/pipeline/context.py`) with OpenAI/Gemini configs, recorder/player options, notifier, and service singletons (notably `IPCVoiceRecorder`).
- The generic pipeline runner (`src/wvcr/pipeline/pipeline.py`) executes ordered `Step` classes (`src/wvcr/pipeline/step.py`) against a mutable `WorkingState` (`src/wvcr/pipeline/state.py`), honoring `requires`/`provides`, timing metrics, and `StepError` recovery.

## Pipeline Definitions (`src/wvcr/modes2`)
- **TranscribePipelineMode** – Initializes run metadata, prepares an output path, configures + records audio, transcribes, saves to `output/transcribe`, copies text to clipboard, and publishes notifications.
- **TranscribeUrlPipelineMode** – Fetches a URL from config/clipboard, downloads audio via `DownloadAudioStep`, then reuses transcription, save, clipboard, and notification steps.
- **ExplainPipelineMode** – Optionally injects a prerecorded instruction; otherwise records/transcribes like the transcribe pipeline, ingests extra “thing” context (clipboard text or Wayland image), calls `ExplainTextStep`, and saves/announces the explanation.

## Step Inventory (`src/wvcr/pipeline/steps`)
- **Bootstrapping** – `InitState`, `PrepareOutputPath`, and `SetKeyFromArg` seed state; `PasteFromClipboard` supports text or Wayland images.
- **Recording** – `ConfigureRecording` merges defaults/CLI overrides, `RecordAudio` calls the IPC recorder, `DownloadAudioStep` handles yt-dlp/ffmpeg extraction.
- **AI calls** – `TranscribeAudioStep` selects OpenAI vs Gemini via `ctx.get_stt_config()`. `ExplainTextStep` delegates to the text-processing service.
- **Outputs** – `SaveTranscript`, `SaveExplanation`, `CopyToClipboard`, `Notify`/`NotifyTranscription`, and `Finalize` (records elapsed time).

## Audio & IPC Stack
- `IPCVoiceRecorder` (`src/wvcr/ipc_recorder.py`) captures microphone audio through `IPCMicHandler`, which spins up a Unix-domain socket server (`UnixAudioInput`) plus a forked `_capture_worker` (both in `src/wvcr/ipc/audio_ipc.py`). The worker streams VAD-filtered PCM frames (Silero-based by default in `src/wvcr/services/vad.py`).
- Keyboard stop monitoring lives in `src/wvcr/common.py` (pynput by default; optional evdev for Wayland). Playback utilities include `SpeechPlayer` (`src/wvcr/player.py`) and low-latency streaming components in `src/wvcr/standalone/audio_player.py`.
- Voiceover flows (`src/wvcr/voiceover.py` + `src/wvcr/test_audio.py`) read clipboard text, request OpenAI TTS audio, and optionally play or store WAV output under `output/voiceover`.

## Service Layer (`src/wvcr/services`)
- `transcription_service.py` abstracts Whisper vs Gemini STT, including MIME-aware uploads and temperature control.
- `text_processing_service.py` implements answer/explain prompts, reusing recent transcripts/answers via `Messages` (`src/wvcr/messages.py`).
- `download_service.py` retrieves remote audio (URL or YouTube) and re-encodes via ffmpeg. `file_service.py` centralizes timestamped naming for transcripts, recordings, downloads, and voiceovers.
- `notification_manager.py` wraps Plyer system notifications; `_clipboard.py` adds Wayland-friendly image extraction.

## Standalone Google ADK Client (`src/wvcr/standalone`)
- Dataclasses in `standalone/config.py` define streaming mode (turn-based vs simultaneous), agent prompts, and voice settings.
- `standalone_client.py` wires `UnixAudioInput`, ADK `EventsReader`, `AudioPlayer`, and the Google mic capture process to stream audio to ADK agents and play low-latency responses.
- `ActivityManager` throttles ADK activity start/end events; `google_search_agent/agent.py` configures Google Search tool usage and prompt templates.

## Testing Status & Gaps
- Pytest modules in `tests/` still reference deprecated types (`AudioConfig`, `TranscriptionHandler`, legacy recorder/player). They currently fail against the modern IPC pipeline and should be updated or removed.
- `src/wvcr/main.py` imports `wvcr.modes.ModeFactory`, which no longer exists; align it with the `modes2` pipelines or drop the entry point to avoid runtime errors.
- `voiceover` and `answer` Hydra pipelines are placeholders; wiring them to the existing `voiceover.py` logic or QA pipeline is still pending.

## Operational Notes
- `.env` loading and API configuration happen in `src/wvcr/config.py`; missing keys will raise runtime errors before any AI calls.
- Outputs are timestamped per mode under `output/<mode>/`, enabling downstream steps (answer/explain) to build history chains quickly.
- Keyboard monitors honor the `WVCR_USE_EVDEV` env var for Wayland reliability. External dependencies: PyAudio, pynput/evdev, pyperclip, OpenAI/Google SDKs, yt-dlp, ffmpeg, silero-vad, Hydra/OmegaConf, fire, and Google ADK.

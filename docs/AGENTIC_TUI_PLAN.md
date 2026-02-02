# Agentic TUI & Pipeline Design Plan
USER:

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         TUI (Standalone)                           │
│  tools/agentic-tui/                                                │
│  ├── main.py          # Textual App                                │
│  ├── config.py        # Load .env                                  │
│  ├── api.py           # ADK API client (list sessions)             │
│  └── requirements.txt # textual, httpx, python-dotenv              │
└───────────────────────────────┬────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │ HTTP (list)     │ subprocess      │
              ▼                 │                 ▼
┌─────────────────────┐         │    ┌─────────────────────────────┐
│   ADK API Server    │         │    │  wvcr agentic --session X   │
│   (External)        │         │    │  --files f1,f2 --text "..." │
│   PostgreSQL        │         │    └──────────────┬──────────────┘
└─────────────────────┘         │                   │ Unix socket
                                │                   ▼
                                │    ┌─────────────────────────────┐
                                │    │      wvcr daemon            │
                                │    │  AgenticPipelineMode        │
                                │    └──────────────┬──────────────┘
                                │                   │ HTTP (run)
                                │                   ▼
                                └──►┌─────────────────────────────┐
                                    │   ADK API Server            │
                                    │   POST /run                 │
                                    └─────────────────────────────┘
```

## 1. Configuration (`.env`)

Add to `.env` and `.env.example`:

```bash
# ADK API Server (for agentic mode)
ADK_API_URL=http://localhost:8000
ADK_APP_NAME=wvcr_agentic
ADK_USER_ID=default_user
```

## 2. Core WVCR Changes

### 2.1 Command Registry (`src/wvcr/commands.py`)
Add `Command.AGENTIC`:
```python
Command.AGENTIC = "agentic"

COMMAND_REGISTRY[Command.AGENTIC] = CommandSpec(
    name=Command.AGENTIC,
    description="Run agentic pipeline via ADK API Server",
    args=["session_id", "instruction", "files", "language"],
    pipeline_mode="AgenticPipelineMode",
)
```

### 2.2 CLI Client (`src/wvcr/cli/client.py`)
Add arguments to `argparse`:
- `--session-id`: String (optional, for ADK session)
- `--files`: String (comma-separated paths)

### 2.3 Pipeline Mode (`src/wvcr/modes2/agentic_pipeline_mode.py`)
New class `AgenticPipelineMode`:
1. `InitState("agentic")`
2. `PrepareOutputPath`
3. **Input Handling**:
   - If `instruction`: `SetKeyFromArg("transcript", instruction)`
   - Else: `ConfigureRecording` -> `RecordAudio` -> `LoadAudioArtifact`
4. **Artifacts**:
   - `LoadFileArtifacts` (New Step)
5. **Execution**:
   - `RunAgenticStep` (New Step - calls ADK API)
6. **Output**:
   - `SaveAgenticResult` (New Step or reuse SaveResearchResult)
   - `CopyToClipboard`
   - `NotifyTranscription`
   - `Finalize`

### 2.4 New Pipeline Steps

**`src/wvcr/pipeline/steps/load_file_artifacts.py`**
- Input: `state["files"]` (string "path1,path2")
- Logic:
  - Split string by comma
  - Validate paths exist
  - Read bytes
  - Create `types.Part` with correct MIME type
- Output: `state["file_parts"]` (list[Part])

**`src/wvcr/pipeline/steps/run_agentic_step.py`**
- Input: `state["transcript"]` OR `state["audio_part"]`, `state["file_parts"]`, `state["session_id"]`
- Logic:
  - Read `ADK_API_URL` from config
  - Construct payload (text/audio + files)
  - POST to `$ADK_API_URL/apps/$APP/users/$USER/sessions/$SESSION/run`
  - Handle streaming or blocking response
- Output: `state["agentic_result"]`

## 3. TUI Application (`tools/agentic-tui/`)

### 3.1 Stack
- **Library**: `textual`
- **HTTP**: `httpx` (async)
- **Config**: `python-dotenv`

### 3.2 Layout
```
┌─────────────────────────────────────────────────────────────┐
│  WVCR Agentic                                         [Q]uit│
├─────────────────────────────────────────────────────────────┤
│ App Name:                                                   │
│ [ Input Field (Manual Entry) ]                              │
│                                                             │
│ Available Apps (Select to fill):                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ weather_agent                                           │ │
│ │ research_agent                                          │ │
│ │ code_reviewer                                           │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Session ID:                                                 │
│ [ Input Field (Manual Entry) ]                              │
│                                                             │
│ Available Sessions (Select to fill ID):                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ses_abc123...                                           │ │
│ │ ses_def456...                                           │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Files (One path per line):                                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ /home/user/docs/spec.pdf                                │ │
│ │ /home/user/images/diagram.png                           │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Instruction (Optional):                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Input field                                             │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ [Run Command]                                               │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 API Endpoints Used

**List available apps:**
```bash
GET $ADK_API_URL/list-apps
# Returns: ["weather_agent", "research_agent", ...]
```

**List sessions for selected app:**
```bash
GET $ADK_API_URL/apps/$APP_NAME/users/$USER_ID/sessions
# Returns: [{"id": "ses_abc123", ...}, ...]
```

### 3.4 Workflow
1. **Startup**:
   - Load `.env`
   - Fetch apps from `GET $ADK_API_URL/list-apps`
   - Populate apps list widget

2. **Interaction**:
VIM style navigation, no mouse, j,k to move, Enter to select.
   - User selects an app in list -> Populates "App Name" input
   - On app selection: Fetch sessions from `GET $ADK_API_URL/apps/$APP/users/$USER/sessions`
   - User selects a session in list -> Populates "Session ID" input
   - OR User types ID manually (new session will be created automatically)
   - User types file paths (multiline)
   - User types instruction

3. **Validation (On "Run" click)**:
   - Check if files exist.
   - If invalid: Show error modal/toast, DO NOT run.
   - If valid: Proceed.

4. **Execution**:
   - Construct command:
     ```bash
     wvcr agentic \
       --app-name "weather_agent" \
       --session-id "ses_..." \
       --files "/path/1,/path/2" \
       --instruction "..."
     ```
   - Execute via `subprocess`
   - Display output in a scrollable log area or standard terminal output
   - "One and gone": Task completes, user can quit or run again.

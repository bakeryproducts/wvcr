# WVCR Daemon Architecture

## Quick Start

```bash
# Start daemon (optional - client auto-starts it)
wvcr-ctl start

# Use client - same as old 'wvcr' command
wvcr transcribe
wvcr explain --instruction "what is this?"
wvcr transcribe-url --url "https://youtube.com/..."
wvcr research --instruction "find info about X"
wvcr voiceover

# Manual daemon control
wvcr-ctl status   # Check status
wvcr-ctl restart  # Restart
wvcr-ctl stop     # Stop
```

## Architecture

### Unified Command Registry
All commands are defined in **one place**: `src/wvcr/commands.py`. The client and daemon both read from this single source of truth.

**Entry points:**
- `wvcr` → lightweight client (auto-starts daemon if needed)
- `wvcr-ctl` → daemon lifecycle management
- `wvcr-daemon` → run daemon directly (usually not needed)

### How It Works

```
wvcr transcribe
  ↓
  Checks if daemon is running
  ↓
  If not: starts it in background (one-time 1-2s delay)
  ↓
  Sends command via Unix socket (~50ms)
  ↓
  Returns result

Daemon (background):
  - All heavy imports pre-loaded at startup
  - Listens on /tmp/wvcr.sock
  - Routes commands using registry
```

## Files

### Core
- `src/wvcr/commands.py` - all commands
- `src/wvcr/daemon/server.py` - Daemon with pre-loaded pipeline modes
- `src/wvcr/daemon/control.py` - Start/stop/status management  
- `src/wvcr/cli/client.py` - Lightweight client 

### Entry Points
- `wvcr` → `wvcr.cli.client:main` (primary interface)
- `wvcr-ctl` → `wvcr.daemon.control:main` (daemon control)
- `wvcr-daemon` → `wvcr.daemon.server:main` (manual daemon)

## Adding New Commands

Only need to edit **one file**: `src/wvcr/commands.py`

```python
# 1. Add to Command enum
class Command(str, Enum):
    MY_NEW_COMMAND = "my-new-command"

# 2. Add to registry
COMMAND_REGISTRY[Command.MY_NEW_COMMAND] = CommandSpec(
    name=Command.MY_NEW_COMMAND,
    description="Does something cool",
    args=["language", "provider"],  # CLI args
    pipeline_mode="MyNewPipelineMode"  # Pipeline class name
)

# 3. Add to user commands list
def get_user_commands() -> list[Command]:
    return [
        ...,
        Command.MY_NEW_COMMAND,
    ]
```

That's it! All three entry points automatically support the new command.

**Request:**
```json
{
  "command": "transcribe",
  "args": {}
}
```

**Response:**
```json
{
  "status": "success",
  "result": "..."
}
```

## Auto-start Daemon (Optional)

Create `~/.config/systemd/user/wvcr-daemon.service`:
```ini
[Unit]
Description=WVCR Voice Recording Daemon

[Service]
ExecStart=/path/to/python -m wvcr.daemon.server
Restart=always

[Install]
WantedBy=default.target
```

Then:
```bash
systemctl --user enable wvcr-daemon
systemctl --user start wvcr-daemon
```

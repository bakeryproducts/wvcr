#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.design import ColorSystem
from textual.widgets import (
    Footer,
    Input,
    TextArea,
    ListView,
    ListItem,
    Label,
    Static,
)

import wvcr.config  # ensure .env is loaded
from wvcr.tui import api

GRUVBOX = ColorSystem(
    primary="#d79921",
    secondary="#458588",
    accent="#b8bb26",
    warning="#d65d0e",
    error="#cc241d",
    success="#98971a",
    background="#282828",
    surface="#3c3836",
    panel="#504945",
    dark=True,
)


class AppListView(ListView):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]


class SessionListView(ListView):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]


class AgenticTUI(App):
    TITLE = "WVCR Agentic"

    CSS = """
    Screen {
        layout: horizontal;
        background: #282828;
    }
    
    #left-panel {
        width: 1fr;
        height: 100%;
        padding: 1;
    }
    
    #right-panel {
        width: 1fr;
        height: 100%;
        padding: 1;
    }
    
    .section-label {
        color: #a89984;
        margin-bottom: 0;
        padding: 0 1;
    }
    
    Input {
        height: 3;
        background: #3c3836;
        border: round #504945;
        padding: 0 1;
    }
    
    Input:focus {
        border: round #d79921;
    }
    
    ListView {
        height: 1fr;
        min-height: 5;
        background: #3c3836;
        border: round #504945;
        padding: 0;
    }
    
    ListView:focus {
        border: round #d79921;
    }
    
    ListView > ListItem {
        padding: 0 1;
    }
    
    ListView > ListItem.--highlight {
        background: #504945;
    }
    
    TextArea {
        height: 1fr;
        min-height: 4;
        background: #3c3836;
        border: round #504945;
    }
    
    TextArea:focus {
        border: round #d79921;
    }
    
    #status {
        height: 1;
        dock: bottom;
        background: #3c3836;
        color: #a89984;
        padding: 0 1;
    }
    
    Footer {
        background: #3c3836;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+r", "run_command", "Run"),
        Binding("ctrl+e", "refresh", "Refresh"),
    ]

    def __init__(self):
        super().__init__()
        self.apps_data: list[str] = []
        self.sessions_data: list[dict] = []
        self.selected_app: str = os.getenv("ADK_APP_NAME", "coordinator")
        self.design = {"dark": GRUVBOX}

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="left-panel"):
                yield Label("App:", classes="section-label")
                yield AppListView(id="apps-list")
                yield Label("Session (empty=new):", classes="section-label")
                yield Input(placeholder="session id", id="session-input")
                yield SessionListView(id="sessions-list")

            with Vertical(id="right-panel"):
                yield Label("Files (one per line):", classes="section-label")
                yield TextArea(id="files-area")
                yield Label("Instruction:", classes="section-label")
                yield TextArea(id="instruction-area")

        yield Static("Ctrl+R: run | Ctrl+E: refresh | Ctrl+Q: quit", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        await self.load_apps()
        await self.load_sessions(self.selected_app)

    async def load_apps(self) -> None:
        self.apps_data = await api.list_apps()
        apps_list = self.query_one("#apps-list", ListView)
        await apps_list.clear()
        for i, app in enumerate(self.apps_data):
            apps_list.append(ListItem(Label(app), id=f"app-{i}"))
        if self.selected_app in self.apps_data:
            idx = self.apps_data.index(self.selected_app)
            apps_list.index = idx

    async def load_sessions(self, app_name: str) -> None:
        if not app_name:
            return
        self.sessions_data = await api.list_sessions(app_name)
        sessions_list = self.query_one("#sessions-list", ListView)
        await sessions_list.clear()
        for i, sess in enumerate(self.sessions_data):
            sess_id = sess.get("id", str(sess))
            sessions_list.append(ListItem(Label(sess_id), id=f"sess-{i}"))

    @on(ListView.Selected, "#apps-list")
    async def on_app_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            idx = int(event.item.id.replace("app-", ""))
            if 0 <= idx < len(self.apps_data):
                self.selected_app = self.apps_data[idx]
                await self.load_sessions(self.selected_app)

    @on(ListView.Selected, "#sessions-list")
    def on_session_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            idx = int(event.item.id.replace("sess-", ""))
            if 0 <= idx < len(self.sessions_data):
                sess = self.sessions_data[idx]
                sess_id = sess.get("id", str(sess))
                session_input = self.query_one("#session-input", Input)
                session_input.value = sess_id

    async def action_run_command(self) -> None:
        await self.run_command()

    async def action_refresh(self) -> None:
        await self.load_apps()
        if self.selected_app:
            await self.load_sessions(self.selected_app)
        self.update_status("Refreshed")

    def update_status(self, msg: str) -> None:
        status = self.query_one("#status", Static)
        status.update(msg)

    async def run_command(self) -> None:
        session_id = self.query_one("#session-input", Input).value.strip()
        files_text = self.query_one("#files-area", TextArea).text.strip()
        instruction = self.query_one("#instruction-area", TextArea).text.strip()

        if not self.selected_app:
            self.update_status("Error: Select an app first")
            return

        files_list = []
        if files_text:
            for line in files_text.splitlines():
                path = line.strip()
                if path:
                    p = Path(path).expanduser()
                    if not p.exists():
                        self.update_status(f"Error: File not found: {path}")
                        return
                    files_list.append(str(p))

        cmd = ["wvcr", "agentic", "--app-name", self.selected_app]

        if session_id:
            cmd.extend(["--session-id", session_id])

        if files_list:
            cmd.extend(["--files", ",".join(files_list)])

        if instruction:
            cmd.extend(["--instruction", instruction])

        self.update_status(f"Running: {' '.join(cmd)}")
        self.exit(result=cmd)


def main():
    app = AgenticTUI()
    result = app.run()

    if result:
        print(f"\nExecuting: {' '.join(result)}\n")
        subprocess.run(result)


if __name__ == "__main__":
    main()

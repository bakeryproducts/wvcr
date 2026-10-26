import io
import json
import re
import subprocess
import time
from pathlib import Path

from PIL import Image

HYPR_CONF = Path.home() / ".config/hypr/hyprland.conf"
TERMINALS = {"alacritty", "kitty", "foot", "wezterm-gui", "ghostty"}
MODS = {"ctrl": "CTRL", "control": "CTRL", "shift": "SHIFT", "alt": "ALT", "super": "SUPER", "win": "SUPER", "meta": "SUPER"}
KEYS = {
    "enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape",
    "backspace": "BackSpace", "tab": "Tab", "space": "space", "delete": "Delete",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "home": "Home", "end": "End", "pageup": "Prior", "pagedown": "Next",
}


def hyprctl(*args: str) -> str:
    return subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5).stdout.strip()


def _json(what: str):
    return json.loads(hyprctl("-j", what) or "{}")


def dispatch(dispatcher: str, arg: str = "") -> None:
    out = hyprctl("dispatch", dispatcher, arg) if arg else hyprctl("dispatch", dispatcher)
    if out != "ok":
        raise RuntimeError(out or "dispatch failed")


def exec_wait(cmd: str, timeout: float = 3.0) -> str:
    before = {c["address"] for c in _json("clients")}
    dispatch("exec", cmd)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.1)
        new = [c for c in _json("clients") if c["address"] not in before and c.get("mapped")]
        if new:
            time.sleep(0.3)
            return f"new window {new[0]['address']}"
    return "started, no new window appeared"


def state() -> str:
    clients = [c for c in _json("clients") if c.get("mapped")]
    active = _json("activewindow").get("address")
    lines = [f"active workspace: {_json('activeworkspace').get('id')}"]
    for c in sorted(clients, key=lambda c: (c["workspace"]["id"], c["at"][0], c["at"][1])):
        mark = " [focused]" if c["address"] == active else ""
        lines.append(f'ws {c["workspace"]["name"]}: {c["address"]} {c["class"]} "{c["title"]}"{mark}')
    return "\n".join(lines)


def client(address: str | None = None) -> dict:
    if not address:
        c = _json("activewindow")
        if not c.get("address"):
            raise RuntimeError("no focused window")
        return c
    for c in _json("clients"):
        if c["address"] == address:
            return c
    raise RuntimeError(f"no window {address}")


def _is_terminal(c: dict) -> bool:
    try:
        return Path(f"/proc/{c['pid']}/comm").read_text().strip() in TERMINALS
    except OSError:
        return False


def _clipboard_text() -> bytes | None:
    types = subprocess.run(["wl-paste", "-l"], capture_output=True, text=True, timeout=2).stdout
    if "text/plain" not in types:
        return None
    return subprocess.run(["wl-paste", "-n"], capture_output=True, timeout=2).stdout


def _copy(data: bytes) -> None:
    subprocess.run(["wl-copy"], input=data, check=True, timeout=2, start_new_session=True)


def type_text(text: str, address: str | None = None) -> None:
    c = client(address)
    if c["address"] != _json("activewindow").get("address"):
        dispatch("focuswindow", f"address:{c['address']}")
        time.sleep(0.15)
    old = _clipboard_text()
    _copy(text.encode())
    mods = "CTRL SHIFT" if _is_terminal(c) else "CTRL"
    dispatch("sendshortcut", f"{mods}, V, address:{c['address']}")
    if old is not None:
        time.sleep(0.4)
        _copy(old)


def press(keys: str, address: str | None = None) -> None:
    c = client(address)
    for combo in keys.split():
        *mods, key = combo.split("+")
        mods = " ".join(MODS.get(m.lower(), m.upper()) for m in mods)
        dispatch("sendshortcut", f"{mods}, {KEYS.get(key.lower(), key)}, address:{c['address']}")
        time.sleep(0.03)


def screenshot(address: str | None = None) -> bytes:
    cmd = ["grim", "-s", "1", "-l", "1"]
    if address != "screen":
        c = client(address)
        if c["workspace"]["id"] != _json("activeworkspace").get("id"):
            raise RuntimeError("window is not on the visible workspace, switch to it first")
        (x, y), (w, h) = c["at"], c["size"]
        cmd += ["-g", f"{x},{y} {w}x{h}"]
    png = subprocess.run([*cmd, "-"], capture_output=True, check=True, timeout=5).stdout
    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buf, "JPEG", quality=75)
    return buf.getvalue()


def binds(path: Path = HYPR_CONF) -> str:
    variables: dict[str, str] = {}
    out = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if m := re.match(r"\$(\w+)\s*=\s*(.*)", line):
            variables[m[1]] = m[2].strip()
            continue
        m = re.match(r"bind[elnrt]*\s*=\s*(.*)", line)
        if not m:
            continue
        body = m[1]
        for k in sorted(variables, key=len, reverse=True):
            body = body.replace(f"${k}", variables[k])
        parts = [p.strip() for p in body.split(",", 3)]
        if len(parts) < 3:
            continue
        mods, key, disp, arg = (parts + [""])[:4]
        combo = "+".join([*mods.split(), key]) if key else mods.replace(" ", "+")
        out.append(f"{combo}: {disp} {arg}".strip())
    return "\n".join(out)

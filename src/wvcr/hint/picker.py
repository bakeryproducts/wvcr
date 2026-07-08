from __future__ import annotations

import os
import subprocess
import sys

CSS = b"""
window {
    background-color: transparent;
}
.card {
    background-color: rgba(45, 45, 58, 0.95);
    border-left: 6px solid #7aa2f7;
    border-radius: 20px;
    padding: 26px 34px;
}
.title {
    color: #7aa2f7;
    font-weight: bold;
    font-size: 16px;
    letter-spacing: 1px;
}
row {
    padding: 18px 24px;
    border-radius: 14px;
}
row .emoji {
    font-size: 56px;
}
row .caption {
    color: #f5f6fa;
    font-size: 18px;
    font-weight: 500;
}
row:selected {
    background-color: rgba(122, 162, 247, 0.35);
}
"""


def _run_gtk(items: list[tuple[str, str, str]]) -> str | None:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, Gtk, GtkLayerShell

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_namespace(win, "wvcr-hint-picker")
    GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.EXCLUSIVE)

    win.set_decorated(False)
    win.set_resizable(False)
    win.set_default_size(320, -1)
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual is not None:
        win.set_visual(visual)
    win.set_app_paintable(True)

    css = Gtk.CssProvider()
    css.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    card.get_style_context().add_class("card")

    title_lbl = Gtk.Label(label="HINT MODE")
    title_lbl.set_halign(Gtk.Align.CENTER)
    title_lbl.get_style_context().add_class("title")
    card.pack_start(title_lbl, False, False, 0)

    listbox = Gtk.ListBox()
    listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
    for _key, emoji, caption in items:
        row = Gtk.ListBoxRow()
        row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        emoji_lbl = Gtk.Label(label=emoji)
        emoji_lbl.set_halign(Gtk.Align.CENTER)
        emoji_lbl.get_style_context().add_class("emoji")
        caption_lbl = Gtk.Label(label=caption)
        caption_lbl.set_halign(Gtk.Align.CENTER)
        caption_lbl.get_style_context().add_class("caption")
        row_box.pack_start(emoji_lbl, False, False, 0)
        row_box.pack_start(caption_lbl, False, False, 0)
        row.add(row_box)
        listbox.add(row)
    card.pack_start(listbox, False, False, 0)

    win.add(card)

    result: dict[str, str | None] = {"key": None}

    def select_row(delta: int) -> None:
        rows = listbox.get_children()
        if not rows:
            return
        current = listbox.get_selected_row()
        idx = current.get_index() if current else -1
        idx = (idx + delta) % len(rows)
        listbox.select_row(rows[idx])

    def confirm() -> None:
        row = listbox.get_selected_row()
        if row is not None:
            result["key"] = items[row.get_index()][0]
        Gtk.main_quit()

    def cancel() -> None:
        result["key"] = None
        Gtk.main_quit()

    def on_key(_widget, event) -> bool:
        keyval = event.keyval
        keyname = Gdk.keyval_name(keyval) or ""
        if keyname in ("Escape",):
            cancel()
            return True
        if keyname in ("Return", "KP_Enter"):
            confirm()
            return True
        if keyname in ("Down", "j"):
            select_row(1)
            return True
        if keyname in ("Up", "k"):
            select_row(-1)
            return True
        return False

    win.connect("key-press-event", on_key)
    win.connect("delete-event", lambda *_a: cancel())

    listbox.select_row(listbox.get_children()[0])
    win.show_all()
    Gtk.main()
    return result["key"]


def main() -> None:
    args = sys.argv[1:]
    items = list(zip(args[0::3], args[1::3], args[2::3]))
    chosen = _run_gtk(items)
    if chosen:
        print(chosen)


def pick(meta: dict[str, tuple[str, str]], system_python: str = "/usr/bin/python3") -> str | None:
    args = []
    for key, (emoji, caption) in meta.items():
        args.append(key)
        args.append(emoji)
        args.append(caption)
    proc = subprocess.run(
        [system_python, os.path.abspath(__file__), *args],
        capture_output=True,
        text=True,
    )
    choice = proc.stdout.strip()
    return choice or None


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import signal
import subprocess
import sys

PIDFILE = "/tmp/wvcr-hint-popup.pid"

CSS = b"""
window {
    background-color: transparent;
}
.card {
    background-color: rgba(45, 45, 58, 0.92);
    border-left: 6px solid %(border)s;
    border-radius: 16px;
    padding: 24px 30px;
}
.title {
    color: %(border)s;
    font-weight: bold;
    font-size: 17px;
    letter-spacing: 1px;
}
.body {
    color: #f5f6fa;
    font-size: 30px;
    font-weight: 500;
}
.close {
    color: #aaa;
    font-size: 22px;
}
.close:hover {
    color: #eceff4;
}
"""


def _run_gtk(title: str, text: str, timeout: float, color: str) -> None:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GLib, Gtk, GtkLayerShell

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.BOTTOM, True)
    GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.LEFT, False)
    GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.RIGHT, False)
    GtkLayerShell.set_margin(win, GtkLayerShell.Edge.BOTTOM, 48)
    GtkLayerShell.set_namespace(win, "wvcr-hint")
    GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.ON_DEMAND)

    win.set_decorated(False)
    win.set_resizable(False)
    win.set_default_size(1, 1)
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual is not None:
        win.set_visual(visual)
    win.set_app_paintable(True)

    css = Gtk.CssProvider()
    css.load_from_data(CSS % {b"border": color.encode()})
    Gtk.StyleContext.add_provider_for_screen(
        screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    def close(*_a):
        win.destroy()
        Gtk.main_quit()
        return True

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.get_style_context().add_class("card")
    card.set_size_request(-1, -1)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    title_lbl = Gtk.Label(label=title.upper())
    title_lbl.set_halign(Gtk.Align.START)
    title_lbl.get_style_context().add_class("title")
    close_btn = Gtk.Button(label="\u2715")
    close_btn.set_relief(Gtk.ReliefStyle.NONE)
    close_btn.get_style_context().add_class("close")
    close_btn.connect("clicked", close)
    header.pack_start(title_lbl, True, True, 0)
    header.pack_end(close_btn, False, False, 0)

    body_lbl = Gtk.Label(label=text)
    body_lbl.set_line_wrap(True)
    body_lbl.set_line_wrap_mode(2)  # PANGO_WRAP_WORD_CHAR
    body_lbl.set_max_width_chars(72)
    body_lbl.set_selectable(True)
    body_lbl.set_halign(Gtk.Align.START)
    body_lbl.set_justify(Gtk.Justification.LEFT)
    body_lbl.get_style_context().add_class("body")

    card.pack_start(header, False, False, 0)
    card.pack_start(body_lbl, False, False, 0)

    outer = Gtk.EventBox()
    outer.add(card)
    outer.connect("button-press-event", lambda w, e: close())
    close_btn.connect("clicked", close)

    win.add(outer)
    win.connect("key-press-event", lambda w, e: close() if e.keyval == Gdk.KEY_Escape else False)

    if timeout and timeout > 0:
        GLib.timeout_add_seconds(int(timeout), close)

    win.show_all()
    Gtk.main()


def _reap_previous() -> None:
    try:
        with open(PIDFILE) as f:
            old_pid = int(f.read().strip())
        os.kill(old_pid, signal.SIGTERM)
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        pass


def _write_pidfile() -> None:
    try:
        with open(PIDFILE, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


def main() -> None:
    title, text, timeout_s, color = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    _reap_previous()
    _write_pidfile()
    try:
        _run_gtk(title, text, timeout_s, color)
    finally:
        try:
            os.remove(PIDFILE)
        except OSError:
            pass


def show_popup(
    title: str,
    text: str,
    timeout: float = 0,
    color: str = "#2ecc71",
    system_python: str = "/usr/bin/python3",
) -> None:
    subprocess.Popen(
        [system_python, os.path.abspath(__file__), title, text, str(timeout), color],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()

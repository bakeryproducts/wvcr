import ctypes
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import GLib, Gtk, GtkLayerShell

COLORS = {
    "connect": "rgba(150, 150, 150, %s)",
    "listen": "rgba(80, 170, 255, %s)",
    "tool": "rgba(80, 220, 140, %s)",
    "think": "rgba(255, 190, 70, %s)",
    "speak": "rgba(190, 110, 255, %s)",
}

CSS = """
window { background-color: transparent; }
.edge {
    border: 2px solid %s;
    border-radius: 10px;
    box-shadow: inset 0 0 14px %s;
}
"""


def _clear_input(win):
    api = ctypes.pythonapi
    api.PyCapsule_GetPointer.restype = ctypes.c_void_p
    api.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
    gdk = ctypes.CDLL("libgdk-3.so.0")
    cairo = ctypes.CDLL("libcairo.so.2")
    cairo.cairo_region_create.restype = ctypes.c_void_p
    gdk.gdk_window_input_shape_combine_region.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    ptr = api.PyCapsule_GetPointer(win.get_window().__gpointer__, None)
    gdk.gdk_window_input_shape_combine_region(ptr, cairo.cairo_region_create(), 0, 0)


def main():
    win = Gtk.Window()
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
        GtkLayerShell.set_anchor(win, edge, True)
    GtkLayerShell.set_exclusive_zone(win, -1)
    GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
    GtkLayerShell.set_namespace(win, "wvcr-live")

    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual is not None:
        win.set_visual(visual)
    win.set_app_paintable(True)

    box = Gtk.Box()
    box.get_style_context().add_class("edge")
    win.add(box)

    css = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_state(name):
        color = COLORS.get(name, COLORS["listen"])
        css.load_from_data((CSS % (color % "0.9", color % "0.45")).encode())

    def on_stdin(source, cond):
        line = source.readline()
        if not line:
            Gtk.main_quit()
            return False
        set_state(line.strip())
        return True

    set_state("connect")
    GLib.io_add_watch(GLib.IOChannel.unix_new(sys.stdin.fileno()), GLib.IO_IN | GLib.IO_HUP, lambda *_: on_stdin(sys.stdin, None))
    win.show_all()
    _clear_input(win)
    Gtk.main()


if __name__ == "__main__":
    main()

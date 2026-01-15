from __future__ import annotations

import subprocess
import shutil
from io import BytesIO
from typing import Iterable, Optional

from PIL import Image


def _which_or_raise(cmd: str) -> str:
    path = shutil.which(cmd)
    if not path:
        raise RuntimeError(f"Required command '{cmd}' not found in PATH.")
    return path


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _enumerate_clipboard_mime_types() -> list[str]:
    """
    Return the list of MIME types currently available in the Wayland clipboard
    (wl-paste --list-types). If wl-paste fails, empty list is returned.
    """
    try:
        cp = _run(["wl-paste", "--list-types"])
    except Exception:
        return []
    raw = cp.stdout.decode("utf-8", "ignore")
    # wl-paste prints one MIME per line
    return [line.strip() for line in raw.splitlines() if line.strip()]


_PREFERRED_IMAGE_TYPES: tuple[str, ...] = (
    "image/png",
    "image/webp",
    "image/jpeg",
    "image/jpg",
)


def _select_image_mime(available: Iterable[str]) -> Optional[str]:
    avail_set = {a.lower() for a in available}
    for t in _PREFERRED_IMAGE_TYPES:
        if t in avail_set:
            return t
    # Fallback: any image/*
    for t in avail_set:
        if t.startswith("image/"):
            return t
    return None


def _paste_linux_wlpaste() -> Image.Image:
    """
    Retrieve an image from the Wayland clipboard (wl-paste) as a PIL.Image.Image.

    Raises:
        RuntimeError if wl-paste not installed, no image data present,
        or decoding fails.
    """
    _which_or_raise("wl-paste")

    mime_types = _enumerate_clipboard_mime_types()
    if not mime_types:
        # Sometimes wl-paste --list-types may not work (old versions); we will still
        # attempt common types directly.
        mime_candidates = list(_PREFERRED_IMAGE_TYPES)
    else:
        selected = _select_image_mime(mime_types)
        if not selected:
            raise RuntimeError("No image MIME type found in clipboard.")
        mime_candidates = [selected]

    last_error: Optional[Exception] = None
    data: Optional[bytes] = None
    used_mime: Optional[str] = None

    for mime in mime_candidates:
        try:
            cp = _run(["wl-paste", "--type", mime])
            if cp.stdout:
                data = cp.stdout
                used_mime = mime
                break
        except subprocess.CalledProcessError as e:
            last_error = e
            continue

    if data is None:
        if last_error:
            raise RuntimeError(f"Failed to read image data from clipboard: {last_error}") from last_error
        raise RuntimeError("No image data available in clipboard.")

    try:
        bio = BytesIO(data)
        img = Image.open(bio)
        print(img.size)
        # Force load so underlying BytesIO can be GC'd
        img.load()
        # Attach source mime if useful
        if used_mime:
            img.info.setdefault("source_mime", used_mime)
        return img
    except Exception as e:
        raise RuntimeError(f"Clipboard data is not a valid image: {e}") from e


__all__ = ["_paste_linux_wlpaste"]


if __name__ == "__main__":
    _paste_linux_wlpaste()
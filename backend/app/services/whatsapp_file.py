"""Send a chat from WhatsApp on this computer.

Click-to-chat leaves the message unsent. This opens the chat, pastes, and presses Enter.
"""

from __future__ import annotations

import base64
import subprocess
import time
from pathlib import Path

from fastapi import HTTPException


def send_text_message(phone: str, text: str) -> None:
    body = (text or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Write the message to send")
    number = "".join(ch for ch in phone if ch.isdigit())
    _open_chat(number)
    hwnd = _wait_for_whatsapp(20)
    if not hwnd:
        raise HTTPException(
            status_code=400,
            detail="WhatsApp did not open. Install WhatsApp, sign in once, and try again.",
        )
    _focus(hwnd)
    time.sleep(4)
    if not _foreground_is_whatsapp():
        raise HTTPException(status_code=400, detail="WhatsApp was not the front window, so the message was not sent.")
    _copy_text(body)
    _chord(0x11, 0x56)
    time.sleep(0.4)
    if not _foreground_is_whatsapp():
        raise HTTPException(status_code=400, detail="WhatsApp moved to the background, so the message was not sent.")
    _tap(0x0D)
    time.sleep(1.2)


def send_video_file(phone: str, video_path: Path, caption: str) -> None:
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="That video is no longer on this computer")
    _copy_file(video_path)
    number = "".join(ch for ch in phone if ch.isdigit())
    _open_chat(number)
    hwnd = _wait_for_whatsapp(20)
    if not hwnd:
        raise HTTPException(
            status_code=400,
            detail="WhatsApp did not open. Install WhatsApp, sign in once, and try again.",
        )
    _focus(hwnd)
    time.sleep(4)
    if not _foreground_is_whatsapp():
        raise HTTPException(status_code=400, detail="WhatsApp was not the front window, so the video was not sent.")
    _chord(0x11, 0x56)  # Ctrl+V pastes the video file
    time.sleep(2)
    if caption.strip() and _foreground_is_whatsapp():
        _copy_text(caption.strip())
        _chord(0x11, 0x56)
        time.sleep(0.4)
    if not _foreground_is_whatsapp():
        raise HTTPException(status_code=400, detail="WhatsApp moved to the background, so the video was not sent.")
    _tap(0x0D)  # Enter sends the video


def _open_chat(number: str) -> None:
    try:
        subprocess.Popen(["cmd", "/c", "start", "", f"whatsapp://send?phone={number}"], close_fds=True)
    except OSError as exc:
        raise HTTPException(status_code=400, detail="WhatsApp could not be opened on this computer") from exc


def _copy_file(path: Path) -> None:
    safe = str(path).replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$files = New-Object System.Collections.Specialized.StringCollection; "
        f"$files.Add('{safe}'); "
        "[System.Windows.Forms.Clipboard]::SetFileDropList($files)"
    )
    _powershell(script)


def _copy_text(text: str) -> None:
    safe = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.Clipboard]::SetText('{safe}')"
    )
    _powershell(script)


def _powershell(script: str) -> None:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise HTTPException(status_code=400, detail="The message could not be placed on the clipboard")


def _wait_for_whatsapp(seconds: int):
    for _ in range(seconds * 2):
        hwnd = _find_whatsapp()
        if hwnd:
            return hwnd
        time.sleep(0.5)
    return None


def _find_whatsapp():
    import ctypes

    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if "whatsapp" in buf.value.lower():
            found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def _focus(hwnd) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.4)


def _foreground_is_whatsapp() -> bool:
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(max(length, 0) + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return "whatsapp" in buf.value.lower()


def _chord(modifier: int, key: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    user32.keybd_event(modifier, 0, 0, 0)
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, 2, 0)
    user32.keybd_event(modifier, 0, 2, 0)


def _tap(key: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, 2, 0)

"""Documented, best-effort Windows desktop controls with optional integrations."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import uuid
from pathlib import Path


def _windows_only() -> None:
    if os.name != "nt":
        raise OSError("This command is available on Windows only.")


def set_volume(level: int) -> None:
    _windows_only()
    if not 0 <= level <= 100:
        raise ValueError("Volume must be between 0 and 100.")
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        endpoint = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        endpoint.SetMasterVolumeLevelScalar(level / 100, None)
    except ImportError as error:
        raise RuntimeError("Volume control dependency is unavailable; reinstall requirements.txt.") from error


def get_volume() -> int:
    _windows_only()
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        endpoint = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        return round(endpoint.GetMasterVolumeLevelScalar() * 100)
    except ImportError as error:
        raise RuntimeError("Volume control dependency is unavailable; reinstall requirements.txt.") from error


def mute(muted: bool) -> None:
    _windows_only()
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        endpoint = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        endpoint.SetMute(int(muted), None)
    except ImportError as error:
        raise RuntimeError("Volume control dependency is unavailable; reinstall requirements.txt.") from error


def set_brightness(level: int) -> None:
    _windows_only()
    if not 0 <= level <= 100:
        raise ValueError("Brightness must be between 0 and 100.")
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
    except ImportError as error:
        raise RuntimeError("Brightness control dependency is unavailable; reinstall requirements.txt.") from error
    except Exception as error:
        raise OSError(f"Brightness control is unsupported on this display: {error}") from error


def screenshot(path: Path) -> None:
    _windows_only()
    if path.exists():
        raise FileExistsError(f"Screenshot already exists: {path}")
    try:
        from PIL import ImageGrab
        image = ImageGrab.grab(all_screens=True)
        image.save(path, format="PNG")
    except ImportError as error:
        raise RuntimeError("Screenshot dependency is unavailable; reinstall requirements.txt.") from error


def clipboard(action: str, text: str = "") -> str:
    _windows_only()
    import tkinter
    root = tkinter.Tk()
    root.withdraw()
    try:
        if action == "copy":
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            return "Text copied to clipboard."
        if action == "clear":
            root.clipboard_clear()
            root.update()
            return "Clipboard cleared."
        if action == "show":
            try:
                return root.clipboard_get()
            except tkinter.TclError:
                return "Clipboard does not contain text."
        raise ValueError("Usage: clipboard <copy <text>|show|clear>")
    finally:
        root.destroy()


def open_settings(category: str) -> None:
    _windows_only()
    pages = {
        "sound": "ms-settings:sound", "display": "ms-settings:display",
        "network": "ms-settings:network", "bluetooth": "ms-settings:bluetooth",
        "storage": "ms-settings:storagesense", "applications": "ms-settings:appsfeatures",
        "updates": "ms-settings:windowsupdate", "personalization": "ms-settings:personalization",
        "privacy": "ms-settings:privacy", "power": "ms-settings:powersleep",
    }
    if category not in pages:
        raise ValueError("Settings category must be: " + ", ".join(pages))
    os.startfile(pages[category])


def open_system_tool(name: str) -> None:
    _windows_only()
    tools = {"taskmanager": "taskmgr.exe", "controlpanel": "control.exe", "startupapps": "ms-settings:startupapps"}
    if name not in tools:
        raise ValueError("Unknown Windows tool.")
    target = tools[name]
    if target.startswith("ms-settings:"):
        os.startfile(target)
    else:
        subprocess.Popen([target], shell=False)


def lock_session() -> None:
    _windows_only()
    if not ctypes.windll.user32.LockWorkStation():
        raise OSError("Windows could not lock the session.")


def sleep_computer() -> None:
    _windows_only()
    if not ctypes.windll.powrprof.SetSuspendState(False, False, False):
        raise OSError("Windows could not enter sleep mode.")


def power_action(action: str) -> None:
    _windows_only()
    flags = {"shutdown": "/s", "restart": "/r"}
    if action not in flags:
        raise ValueError("Unsupported power action.")
    subprocess.Popen(["shutdown.exe", flags[action], "/t", "0"], shell=False)


def open_known_folder(name: str) -> Path:
    _windows_only()
    aliases = {"downloads": "downloads", "desktop": "desktop", "documents": "documents",
               "pictures": "pictures", "videosfolder": "videos", "musicfolder": "music"}
    if name not in aliases:
        raise ValueError("Unknown known folder.")
    path = known_folder_path(aliases[name])
    if not path.is_dir():
        raise FileNotFoundError(f"Folder is unavailable: {path}")
    os.startfile(str(path))
    return path


def known_folder_path(name: str) -> Path:
    """Query a Windows Known Folder, respecting user redirection and OneDrive."""
    _windows_only()
    ids = {
        "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
        "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
        "pictures": "33E28130-4E1E-4676-835A-98395C3BC3BB",
        "videos": "18989B1D-99B5-455B-841C-AB7C74E4DDFC",
        "music": "4BD8D571-6D19-48D3-BE97-422220080E43",
        "downloads": "374DE290-123F-4565-9164-39C4925E467B",
    }
    if name not in ids:
        raise ValueError(f"Unknown known folder: {name}")

    class GUID(ctypes.Structure):
        _fields_ = [("data", ctypes.c_ubyte * 16)]

    folder_id = GUID.from_buffer_copy(uuid.UUID(ids[name]).bytes_le)
    result = ctypes.c_wchar_p()
    function = ctypes.windll.shell32.SHGetKnownFolderPath
    function.argtypes = [ctypes.POINTER(GUID), ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    function.restype = ctypes.c_long
    status = function(ctypes.byref(folder_id), 0, None, ctypes.byref(result))
    if status != 0 or not result.value:
        raise OSError(f"Windows could not resolve the {name} folder (HRESULT {status}).")
    try:
        return Path(result.value)
    finally:
        free_memory = ctypes.windll.ole32.CoTaskMemFree
        free_memory.argtypes = [ctypes.c_void_p]
        free_memory(ctypes.cast(result, ctypes.c_void_p))


def reveal_file(path: Path) -> None:
    _windows_only()
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if path.is_dir():
        os.startfile(str(path))
    else:
        subprocess.Popen(["explorer.exe", "/select,", str(path)], shell=False)

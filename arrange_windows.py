"""Arrange this app's previews without touching Telegram or camera capture."""
import ctypes
import sys
from ctypes import wintypes

from monkeyfacesmeme.windowing import focus_window, lock_capture_window


def preview_layout(width, height):
    """Positions in the desktop work area; preserve the 720px capture client."""
    return None, (max(0, width - 752), 32)


def arrange():
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    area = wintypes.RECT()
    if not user32.SystemParametersInfoW(48, 0, ctypes.byref(area), 0):
        return
    _, output = preview_layout(area.right - area.left, area.bottom - area.top)
    main_window = user32.FindWindowW(None, 'MonkeyFacesMeme')
    if user32.FindWindowW(None, 'MonkeyFacesMeme Output'):
        lock_capture_window('MonkeyFacesMeme Output', 720)
    if main_window:
        focus_window('MonkeyFacesMeme')
    print('Main window stays fullscreen; OBS output stays fixed at 720x720.')


def close_app_windows():
    """Ask HighGUI to close cleanly so main.py can release all resources."""
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    for title in ('MonkeyFacesMeme Output', 'MonkeyFacesMeme'):
        window = user32.FindWindowW(None, title)
        if window:
            user32.PostMessageW(window, 0x0010, 0, 0)
    print('MonkeyFacesMeme windows were asked to close cleanly.')


if __name__ == '__main__':
    close_app_windows() if '--close' in sys.argv else arrange()

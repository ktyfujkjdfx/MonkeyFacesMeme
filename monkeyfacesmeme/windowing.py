"""Small Windows helpers for the main view and the OBS capture view."""

import os


def _user32():
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    return user32


def lock_capture_window(title, size=720):
    """Keep the OBS source square, non-maximizable and behind the main view."""
    if os.name != "nt":
        return True
    import ctypes
    from ctypes import wintypes

    user32 = _user32()
    window = user32.FindWindowW(None, title)
    if not window:
        return False

    gww_style, gww_exstyle = -16, -20
    ws_thickframe, ws_minimizebox, ws_maximizebox = 0x00040000, 0x00020000, 0x00010000
    ws_ex_toolwindow, ws_ex_noactivate = 0x00000080, 0x08000000
    style = user32.GetWindowLongW(window, gww_style)
    style &= ~(ws_thickframe | ws_minimizebox | ws_maximizebox)
    user32.SetWindowLongW(window, gww_style, style)
    exstyle = user32.GetWindowLongW(window, gww_exstyle)
    user32.SetWindowLongW(window, gww_exstyle,
                          exstyle | ws_ex_toolwindow | ws_ex_noactivate)

    window_rect, client_rect, area = wintypes.RECT(), wintypes.RECT(), wintypes.RECT()
    user32.GetWindowRect(window, ctypes.byref(window_rect))
    user32.GetClientRect(window, ctypes.byref(client_rect))
    user32.SystemParametersInfoW(48, 0, ctypes.byref(area), 0)
    frame_width = (window_rect.right - window_rect.left) - client_rect.right
    frame_height = (window_rect.bottom - window_rect.top) - client_rect.bottom
    width, height = size + frame_width, size + frame_height
    x = max(area.left, area.right - width - 16)
    y = area.top + 16

    hwnd_bottom = 1
    sw_shownoactivate = 4
    swp_noactivate, swp_framechanged = 0x0010, 0x0020
    user32.ShowWindow(window, sw_shownoactivate)
    user32.SetWindowPos(window, hwnd_bottom, x, y, width, height,
                        swp_noactivate | swp_framechanged)
    return True


def focus_window(title):
    """Return keyboard focus to the user-facing window without resizing it."""
    if os.name != "nt":
        return True
    user32 = _user32()
    window = user32.FindWindowW(None, title)
    if not window:
        return False
    user32.BringWindowToTop(window)
    user32.SetForegroundWindow(window)
    return True

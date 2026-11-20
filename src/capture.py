"""Chụp một vùng màn hình bằng mss (hỗ trợ Windows/macOS/Linux)."""

import mss
from PIL import Image


def capture_region(region):
    """Chụp vùng màn hình.

    region: dict {"left": int, "top": int, "width": int, "height": int}
    Trả về PIL.Image (RGB).
    """
    with mss.mss() as sct:
        shot = sct.grab(region)
        # mss trả về BGRA; chuyển sang RGB cho PIL
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def list_monitors():
    """Danh sách màn hình (phần tử 0 là toàn bộ desktop gộp)."""
    with mss.mss() as sct:
        return list(sct.monitors)


def screen_size():
    """Kích thước màn hình chính (width, height)."""
    with mss.mss() as sct:
        mon = sct.monitors[1]  # màn hình chính
        return mon["width"], mon["height"]

"""Điểm khởi chạy: PS5 Dịch Game — phụ đề tiếng Việt trực tiếp cho game PS5.

Cách dùng:
1. Bật PS5 và mở app PS Remote Play chính thức của Sony trên laptop
   (nên đăng nhập bằng tài khoản PSN phụ để tay cầm chính vẫn chơi trên TV).
2. Mở app này, bấm "Chọn vùng phụ đề" và kéo chuột chọn vùng chữ tiếng Anh
   trong cửa sổ Remote Play.
3. Bấm "Bắt đầu dịch" — bản dịch tiếng Việt hiện ở thanh phụ đề nổi.
"""

from .gui import run_app
from .ocr import configure_tesseract


def main():
    tesseract_path = configure_tesseract()
    run_app(tesseract_path=tesseract_path)


if __name__ == "__main__":
    main()

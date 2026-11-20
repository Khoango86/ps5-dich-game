"""OCR tiếng Anh bằng Tesseract (qua pytesseract).

Tiền xử lý: xám -> phóng to 2x -> tăng tương phản -> nhị phân -> đảo màu
nếu nền tối (phụ đề game thường là chữ trắng trên nền đen).
"""

import os
import shutil
import sys

import pytesseract
from PIL import Image, ImageOps


def find_tesseract():
    """Tìm đường dẫn tới tesseract (tesseract.exe trên Windows).

    Thứ tự ưu tiên:
    1. Biến môi trường TESSERACT_CMD
    2. Bản Tesseract đóng gói kèm app (PyInstaller: sys._MEIPASS/tesseract)
    3. tesseract trong PATH hệ thống
    4. Đường dẫn cài đặt mặc định trên Windows
    Trả về đường dẫn đầy đủ, hoặc None nếu không tìm thấy.
    """
    env = os.environ.get("TESSERACT_CMD")
    if env and os.path.isfile(env):
        return env

    candidates = []
    if getattr(sys, "frozen", False):
        # Chạy từ file .exe đóng gói bằng PyInstaller
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates.append(os.path.join(base, "tesseract", "tesseract.exe"))
        candidates.append(
            os.path.join(os.path.dirname(sys.executable), "tesseract", "tesseract.exe")
        )

    which = shutil.which("tesseract")
    if which:
        candidates.append(which)

    candidates.append(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    candidates.append(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")

    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def configure_tesseract():
    """Cấu hình pytesseract trỏ tới tesseract tìm được.

    Trả về đường dẫn tesseract, hoặc None nếu không tìm thấy.
    Nếu dùng bản đóng gói kèm app thì đặt thêm TESSDATA_PREFIX.
    """
    path = find_tesseract()
    if path is None:
        return None
    pytesseract.pytesseract.tesseract_cmd = path
    tessdata = os.path.join(os.path.dirname(path), "tessdata")
    if os.path.isdir(tessdata):
        os.environ.setdefault("TESSDATA_PREFIX", tessdata)
    return path


def preprocess(image):
    """Tiền xử lý ảnh trước khi OCR, trả về ảnh nhị phân (đen/trắng)."""
    gray = image.convert("L")
    w, h = gray.size
    gray = gray.resize((w * 2, h * 2), Image.LANCZOS)
    gray = ImageOps.autocontrast(gray)
    bw = gray.point(lambda p: 255 if p > 150 else 0)
    # Nếu nền tối (chữ trắng trên nền đen) -> đảo thành chữ đen trên nền trắng,
    # vì Tesseract đọc tốt hơn khi chữ tối trên nền sáng.
    hist = bw.histogram()
    if hist[255] < hist[0]:
        bw = ImageOps.invert(bw)
    return bw


def clean_text(text):
    """Dọn text OCR: gộp các dòng, bỏ khoảng trắng thừa, bỏ rác."""
    lines = [ln.strip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]
    joined = " ".join(lines)
    joined = " ".join(joined.split())
    # Bỏ các ký tự rác thường gặp do OCR nhầm (giữ chữ, số, dấu câu cơ bản)
    allowed = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        " .,!?;:'\"()-_/%$#@&"
    )
    joined = "".join(ch for ch in joined if ch in allowed)
    joined = " ".join(joined.split())
    # Cần ít nhất 2 ký tự chữ thì mới coi là có nội dung
    letters = sum(1 for ch in joined if ch.isalpha())
    if letters < 2:
        return ""
    return joined


def ocr_image(image):
    """OCR một ảnh PIL, trả về text tiếng Anh đã dọn sạch ("" nếu không đọc được)."""
    processed = preprocess(image)
    raw = pytesseract.image_to_string(processed, lang="eng", config="--psm 6")
    return clean_text(raw)

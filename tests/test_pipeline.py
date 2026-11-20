"""Test end-to-end: OCR -> dịch, cache, và logic chống lặp/debounce.

Chạy từ thư mục gốc dự án:
    .venv/bin/python tests/test_pipeline.py

Yêu cầu: Tesseract đã cài (tesseract trong PATH).
Phần dịch trực tiếp (live) cần mạng và dịch vụ không bị giới hạn — trên máy
chủ dùng chung IP này, Google/MyMemory có thể trả 429 (hết hạn mức IP dùng
chung); khi đó test live báo SKIP chứ không FAIL, và phần logic dịch được
kiểm chứng bằng test giả lập (mock) bên dưới.
"""

import os
import sys
from unittest import mock

# Windows: stdout mặc định là cp1252, in tiếng Việt sẽ văng lỗi
# UnicodeEncodeError ngay dòng in đầu tiên (test trên GitHub Actions fail
# sau ~1 giây vì vậy). Ép stdout/stderr sang UTF-8 ngay từ đầu.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from make_test_image import SUBTITLE_1, SUBTITLE_2, SUBTITLE_REGION  # noqa: E402
from make_test_image import make_game_image  # noqa: E402
from src.ocr import clean_text, configure_tesseract, ocr_image  # noqa: E402
from src.pipeline import TextStabilizer  # noqa: E402
from src.translate import Translator  # noqa: E402

failures = []
skipped = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def skip(name, reason):
    print(f"[SKIP] {name} — {reason}")
    skipped.append(name)


def test_ocr(image_path, expected_words):
    img = Image.open(image_path)
    crop = img.crop(SUBTITLE_REGION)
    text = ocr_image(crop)
    print(f"  OCR ({os.path.basename(image_path)}): {text!r}")
    found = [w for w in expected_words if w.lower() in text.lower()]
    check(
        f"OCR đọc được phụ đề ({os.path.basename(image_path)})",
        len(found) >= len(expected_words) - 1,
        f"tìm thấy {len(found)}/{len(expected_words)} từ khóa: {found}",
    )
    return text


def test_translate_mock():
    """Kiểm chứng logic dịch bằng mock (không cần mạng)."""
    tr = Translator()
    # 1. Google trả về bình thường
    with mock.patch.object(
        tr._google, "translate",
        return_value="Chúng ta cần rời khỏi Vice City trước bình minh.",
    ):
        out = tr.translate("We need to get out of Vice City before dawn.")
        check(
            "Dịch (mock Google): trả đúng bản dịch",
            out == "Chúng ta cần rời khỏi Vice City trước bình minh.",
            repr(out),
        )
        # 2. Cache: gọi lại không gọi Google nữa
        with mock.patch.object(tr._google, "translate",
                               side_effect=Exception("không được gọi")):
            out2 = tr.translate("We need to get out of Vice City before dawn.")
        check("Cache (mock): câu đã dịch lấy từ cache",
              out2 == out and tr.cache_size == 1)
    # 3. Google lỗi -> rơi xuống MyMemory
    tr2 = Translator()
    with mock.patch.object(tr2._google, "translate",
                           side_effect=Exception("429")), mock.patch(
        "src.translate.requests.get"
    ) as fake_get:
        fake_resp = mock.Mock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "responseData": {"translatedText": "Lô hàng đến lúc nửa đêm."}
        }
        fake_get.return_value = fake_resp
        out3 = tr2.translate("The shipment arrives at midnight.")
        check("Fallback (mock): Google lỗi thì dùng MyMemory",
              out3 == "Lô hàng đến lúc nửa đêm.", repr(out3))
    # 4. MyMemory trả cảnh báo hết hạn mức -> phải lọc ra, không hiện như bản dịch
    tr3 = Translator()
    with mock.patch.object(tr3._google, "translate",
                           side_effect=Exception("429")), mock.patch(
        "src.translate.requests.get"
    ) as fake_get:
        fake_resp = mock.Mock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "responseData": {
                "translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE "
                "TRANSLATIONS FOR TODAY."
            }
        }
        fake_get.return_value = fake_resp
        out4 = tr3.translate("Hello world.")
        check("Lọc cảnh báo MyMemory: không hiện cảnh báo như bản dịch",
              out4 == "", repr(out4))


def test_translate_live(text):
    """Thử dịch thật. Nếu dịch vụ giới hạn IP dùng chung thì báo SKIP."""
    tr = Translator()
    vi = tr.translate(text)
    print(f"  Dịch live: {vi!r}")
    if not vi:
        skip(
            "Dịch live EN->VI",
            "Google (429) và MyMemory (hết hạn mức ngày) đều giới hạn IP "
            "dùng chung của máy chủ test — chưa kiểm chứng được trực tiếp, "
            "cần test lại trên mạng nhà người dùng.",
        )
        return
    check("Dịch live EN->VI ra tiếng Việt", len(vi) > 10, f"dài {len(vi)} ký tự")
    check("Dịch live giữ nguyên tên riêng 'Vice City'", "Vice City" in vi)


def test_stabilizer():
    st = TextStabilizer(debounce=0.3)
    check("Debounce: text mới chưa dịch ngay", st.observe("A", 0.0) is None)
    check("Debounce: chưa đủ 0,3s thì chưa dịch", st.observe("A", 0.1) is None)
    check("Debounce: ổn định 0,3s thì dịch", st.observe("A", 0.35) == "A")
    check("Chống lặp: câu đã dịch không dịch lại", st.observe("A", 0.5) is None)
    check("Debounce: câu mới chờ ổn định", st.observe("B", 0.6) is None)
    check("Debounce: câu mới ổn định thì dịch", st.observe("B", 0.95) == "B")
    check("Xóa phụ đề: text rỗng chờ ổn định", st.observe("", 1.0) is None)
    check("Xóa phụ đề: rỗng ổn định thì báo xóa", st.observe("", 1.4) == "")
    # unmark: sau khi dịch lỗi, câu cũ được dịch lại
    st2 = TextStabilizer(debounce=0.3)
    st2.observe("C", 0.0)
    check("unmark: câu ổn định thì dịch", st2.observe("C", 0.4) == "C")
    st2.unmark()
    check("unmark: sau khi quên thì dịch lại được", st2.observe("C", 0.8) == "C")


def test_clean_text():
    check("clean_text: chuỗi rỗng", clean_text("") == "")
    check("clean_text: gộp dòng", clean_text("Hello\n  world ") == "Hello world")
    check("clean_text: bỏ rác", clean_text("@#$") == "")


def main():
    print("== 0. Tìm Tesseract ==")
    # Quan trọng: phải gọi configure_tesseract() để pytesseract trỏ đúng tới
    # tesseract đã cài (kể cả khi tesseract không có trong PATH, như trên
    # GitHub Actions sau khi cài im lặng — nó sẽ dùng đường dẫn mặc định
    # C:\Program Files\Tesseract-OCR\tesseract.exe).
    tess_path = configure_tesseract()
    if tess_path is None:
        print("  LỖI: không tìm thấy Tesseract (chưa cài hoặc sai đường dẫn).")
        return 1
    print(f"   Tesseract: {tess_path}")

    print("== 1. Tạo ảnh test ==")
    img1 = make_game_image(SUBTITLE_1, os.path.join(ASSETS, "game_subtitle_1.png"))
    img2 = make_game_image(SUBTITLE_2, os.path.join(ASSETS, "game_subtitle_2.png"))
    print(f"   {img1}\n   {img2}")

    print("== 2. OCR (Tesseract thật) ==")
    text1 = test_ocr(img1, ["Vice City", "dawn", "Follow", "quiet"])
    text2 = test_ocr(img2, ["shipment", "midnight", "late"])

    print("== 3. Dịch (mock — kiểm chứng logic) ==")
    test_translate_mock()

    print("== 4. Dịch live (thử thật, có thể SKIP nếu bị giới hạn) ==")
    test_translate_live(text1)
    print(f"   (OCR ảnh 2 để tham khảo: {text2!r})")

    print("== 5. Chống lặp / debounce ==")
    test_stabilizer()

    print("== 6. Dọn text ==")
    test_clean_text()

    print()
    print(f"KẾT QUẢ: {len(failures)} FAIL, {len(skipped)} SKIP")
    if failures:
        print(f"  FAIL: {failures}")
        return 1
    if skipped:
        print(f"  SKIP: {skipped}")
    print("  Tất cả test kiểm chứng được đều PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Kết quả test — PS5 Dịch Game v1

Ngày test: 2026-11-20.

## Môi trường test

- Máy chủ Linux (Ubuntu, VM headless — không có màn hình, không có PS5).
- Python 3.12.3, venv riêng.
- Tesseract 5.3.4 (cài bằng apt) + dữ liệu tiếng Anh.
- Ảnh test tự tạo bằng `tests/make_test_image.py`: ảnh 1280x720 giả lập màn
  hình game ban đêm (nhà cao tầng, thanh máu, minimap, dòng mục tiêu) với
  phụ đề chữ trắng đậm 2 dòng ở cuối màn hình.

Chạy test: `.venv/bin/python tests/test_pipeline.py` (từ thư mục gốc dự án).

## Kết quả (lần chạy cuối: 0 FAIL, 1 SKIP)

| Hạng mục | Kết quả | Ghi chú |
|---|---|---|
| `py_compile` toàn bộ module (src + tests + run.py) | ✅ PASS | Không lỗi cú pháp |
| Import toàn bộ module (core + GUI) | ✅ PASS | Import được, không cần màn hình |
| OCR ảnh 1 (phụ đề 2 dòng) | ✅ PASS | Đọc đúng 100%: "We need to get out of Vice City before dawn. Follow me, and stay quiet." — 4/4 từ khóa |
| OCR ảnh 2 (phụ đề khác) | ✅ PASS | Đọc đúng 100%: "The shipment arrives at midnight. Don't be late." — 3/3 từ khóa |
| Dịch (mock Google) | ✅ PASS | Trả đúng bản dịch giả lập |
| Cache dịch (mock) | ✅ PASS | Dịch lại cùng câu lấy từ cache, không gọi dịch vụ |
| Fallback Google lỗi → MyMemory (mock) | ✅ PASS | Tự đổi dịch vụ khi Google lỗi |
| Lọc cảnh báo hết hạn mức MyMemory (mock) | ✅ PASS | Cảnh báo "MYMEMORY WARNING" không bị hiện như bản dịch |
| Debounce 0,3s (text ổn định mới dịch) | ✅ PASS | 8/8 trường hợp, kể cả xóa phụ đề khi text rỗng |
| Chống lặp (không dịch lại câu cũ) | ✅ PASS | Câu đã dịch không dịch lại |
| Dịch lại sau khi lỗi (unmark) | ✅ PASS | Sau `unmark()`, câu cũ được dịch lại |
| Dọn text OCR (`clean_text`) | ✅ PASS | Chuỗi rỗng, gộp dòng, bỏ ký tự rác |
| **Dịch live EN→VI (gọi thật)** | ⚠️ **SKIP** | Xem bên dưới |

## Vì sao test dịch live bị SKIP (không phải lỗi code)

Máy chủ test dùng chung một IP ra mạng cho nhiều người dùng:

- **Google Translate (endpoint không chính thức)**: trả **HTTP 429 Too Many
  Requests** — IP dùng chung đã bị Google giới hạn. Kiểm chứng bằng curl:
  `translate.googleapis.com` trả 429.
- **MyMemory**: trả cảnh báo "YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR
  TODAY" (hết 5.000 ký tự/ngày của IP dùng chung, kể cả khi kèm email).
- Thử thêm 2 dịch vụ khác (Argos/LibreTranslate, Lingva) cũng không dùng
  được từ máy chủ này (timeout / provider unavailable).

Logic dịch (gọi Google → lỗi thì đổi MyMemory → cache → lọc cảnh báo) đã
được kiểm chứng bằng test mock. **Dịch live cần test lại trên mạng nhà
người dùng** (IP nhà riêng thường không bị giới hạn như IP máy chủ dùng
chung).

## Những gì CHƯA test được ở đây (cần test trên máy thật)

- **Giao diện Windows thật**: cửa sổ tkinter, thanh phụ đề trong suốt luôn
  nổi trên cùng, chọn vùng bằng kéo chuột — code đã viết cẩn thận và
  import được, nhưng chưa chạy thử trên Windows có màn hình.
- **Chụp màn hình thật bằng `mss` trên Windows** (VM này không có X server).
- **Vòng lặp pipeline trực tiếp** (chụp → OCR → dịch liên tục) — chỉ mới
  test từng khối rời (OCR ảnh tĩnh, logic debounce, logic dịch).
- **PS Remote Play thật + game PS5 thật**: chưa có PS5 để test.
- **File .exe đóng gói**: build bằng GitHub Actions (chưa chạy thử trên
  laptop người dùng).
- **Dịch live** (như trên).

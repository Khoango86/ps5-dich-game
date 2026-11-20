# PS5 Dịch Game — Phụ đề tiếng Việt trực tiếp cho game PS5

Phần mềm Windows giúp chơi game PS5 bằng tiếng Việt: app đọc chữ phụ đề
tiếng Anh trong game rồi dịch sang tiếng Việt và hiện ngay trên màn hình
lúc đang chơi.

> **Không hack máy, không sửa file game.** Máy PS5 vẫn zin, game vẫn bản gốc.
> App chỉ đọc chữ đang hiện trên màn hình rồi dịch — giống như có người ngồi
> cạnh dịch phụ đề cho mình vậy.

Bản này được viết lại từ đầu (clean-room) chỉ bằng thư viện mã nguồn mở,
không dùng code hay máy chủ của bất kỳ phần mềm thương mại nào.

## Cách hoạt động

1. Bạn chơi PS5 trên TV như bình thường.
2. Trên laptop Windows, mở app **PS Remote Play** chính thức của Sony
   (đăng nhập bằng **tài khoản PSN phụ** để tay cầm chính vẫn chơi trên TV).
3. App này chụp vùng phụ đề trong cửa sổ Remote Play → đọc chữ bằng
   Tesseract OCR → dịch Anh–Việt bằng Google Translate (dự phòng MyMemory)
   → hiện bản dịch ở thanh phụ đề nổi trên màn hình laptop.

## Cần chuẩn bị

- Laptop Windows 10/11, có mạng.
- PS5 đã bật **Chơi từ xa** (Cài đặt → Hệ thống → Chơi từ xa → Bật).
- App **PS Remote Play** của Sony (tải miễn phí tại
  https://www.playstation.com/remote-play/), đăng nhập tài khoản PSN phụ.
- PS5 và laptop cùng mạng Wi-Fi (lần ghép đầu tiên).

## Cách 1 — Dùng file .exe (khuyên dùng, không cần cài gì thêm)

1. Vào mục **Releases** của repo này, tải file `PS5-Dich-Game.exe` mới nhất.
2. Nháy đúp chạy. (Lần đầu chạy có thể hơi chậm vì file tự bung Tesseract
   đi kèm — khoảng 10–20 giây. Windows SmartScreen có thể hỏi, bấm
   "More info" → "Run anyway".)
3. Tesseract đã đóng gói sẵn trong file .exe nên không cần cài thêm.

## Cách 2 — Chạy từ code nguồn

1. Cài Python 3.10+ từ https://www.python.org/downloads/
   (lúc cài nhớ tick **Add python.exe to PATH**).
2. Tải code về, nháy đúp `setup.bat` — nó sẽ tự cài thư viện, thử cài
   Tesseract bằng winget (nếu chưa có) rồi mở app.
3. Nếu `setup.bat` không cài được Tesseract tự động: tải bản cài tại
   https://github.com/UB-Mannheim/tesseract/wiki
   (file `tesseract-ocr-w64-setup-*.exe`), cài xong chạy lại `setup.bat`.

## Hướng dẫn dùng (lần đầu)

1. Bật PS5, mở game.
2. Trên laptop, mở **PS Remote Play** và kết nối tới PS5 (tài khoản phụ).
   Để cửa sổ Remote Play hiện rõ hình game.
3. Mở **PS5 Dịch Game**.
4. Bấm **Chọn vùng phụ đề…**, kéo chuột vẽ hình chữ nhật bao quanh vùng chữ
   phụ đề tiếng Anh trong cửa sổ Remote Play (thường là dòng chữ ở cuối
   màn hình game). Nhấn Esc nếu muốn hủy chọn.
5. Bấm **▶ Bắt đầu dịch**.
6. Khi game hiện lời thoại, bản dịch tiếng Việt sẽ hiện ở thanh phụ đề nổi
   (kéo thả thanh phụ đề tới chỗ nào tiện nhìn), đồng thời hiện trong bảng
   điều khiển ở ô **Tiếng Việt (dịch)**.
7. Chỉnh **cỡ chữ** nếu muốn chữ to/nhỏ hơn. Bấm **⏹ Dừng** khi không cần.

## Mẹo để dịch tốt

- **Chọn vùng phụ đề vừa khít dòng chữ**, đừng bao cả thanh máu/minimap —
  càng ít chữ thừa, OCR càng chính xác.
- Bật phụ đề trong game (thường ở Settings → Subtitles/Dialogue).
- Để cửa sổ Remote Play ở độ phân giải cao, không thu nhỏ quá.
- Nếu một câu dịch sai, thường do OCR đọc sai chữ — thử chọn lại vùng cho
  khít hơn.

## Giới hạn đã biết (v1)

- Phụ đề chỉ hiện trên **màn hình laptop**, chưa hiện lên TV (xem mục
  Giai đoạn 2 bên dưới).
- Dịch bằng Google Translate miễn phí (không cần key): đôi khi Google tạm
  giới hạn nếu dịch quá nhiều trong thời gian ngắn — app sẽ tự thử lại
  sau 5 giây, rồi tự đổi sang MyMemory.
- MyMemory miễn phí ẩn danh giới hạn 5.000 ký tự/ngày/IP. (Bản sau sẽ cho
  nhập email để nâng lên 50.000 ký tự/ngày.)
- Game không có phụ đề thì app không dịch được (app chỉ đọc chữ hiện trên
  màn hình, không dịch giọng nói).
- Chỉ hỗ trợ màn hình chính khi chọn vùng.

## Chạy test

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python tests/test_pipeline.py
```

Chi tiết kết quả test xem `TESTS.md`.

## Cấu trúc dự án

```
run.py                  Điểm khởi chạy (python run.py)
setup.bat               Cài đặt 1 lần bấm trên Windows (chạy từ code)
src/
  main.py               Khởi tạo Tesseract + mở bảng điều khiển
  gui.py                Bảng điều khiển (chọn vùng, bắt đầu/dừng, cỡ chữ)
  overlay.py            Thanh phụ đề nổi, trong suốt, luôn trên cùng
  region_picker.py      Chọn vùng phụ đề bằng cách kéo chuột
  capture.py            Chụp vùng màn hình (mss)
  ocr.py                OCR tiếng Anh (Tesseract) + tiền xử lý ảnh
  translate.py          Dịch EN->VI (Google, dự phòng MyMemory) + cache
  pipeline.py           Luồng nền: chụp -> OCR -> chống lặp -> dịch
tests/
  make_test_image.py    Tạo ảnh giả lập màn hình game có phụ đề
  test_pipeline.py      Test OCR thật + logic dịch + chống lặp/debounce
.github/workflows/
  build-windows.yml     GitHub Actions: build file .exe cho Windows
```

## Giai đoạn 2 (dự kiến)

- **App Tizen cho TV Samsung**: hiện phụ đề tiếng Việt ngay trên TV
  (TV nhận phụ đề từ laptop qua mạng nội bộ, vẽ đè lên hình game HDMI),
  cài qua Developer Mode.
- Nhập email MyMemory trong Cài đặt để nâng hạn mức dịch.
- Tùy chọn dịch vụ dịch khác, lưu lịch sử phụ đề.

## Giấy phép

MIT — xem file `LICENSE`.

"""Luồng chạy nền: chụp -> OCR -> chống lặp -> dịch -> đẩy kết quả ra GUI.

- Chống lặp: chỉ dịch khi text OCR thay đổi so với câu đã dịch.
- Debounce: text phải ổn định (không đổi) ít nhất `debounce` giây mới dịch,
  tránh dịch những khung hình đang chuyển cảnh hoặc OCR chưa ổn định.
- Khi phụ đề biến mất (OCR ra ""), gửi tín hiệu xóa phụ đề.
"""

import threading
import time

from .capture import capture_region
from .ocr import ocr_image
from .translate import Translator


class TextStabilizer:
    """Quyết định khi nào một text OCR đủ ổn định để dịch.

    observe(text, now) trả về text cần dịch, hoặc None nếu chưa đủ điều kiện.
    """

    def __init__(self, debounce=0.3):
        self.debounce = debounce
        self._pending_text = None
        self._pending_since = 0.0
        self._last_text = ""

    def observe(self, text, now):
        if text != self._pending_text:
            self._pending_text = text
            self._pending_since = now
            return None
        if text != self._last_text and (now - self._pending_since) >= self.debounce:
            self._last_text = text
            return text
        return None

    def unmark(self):
        """Quên câu vừa dịch để lần observe sau có thể dịch lại.

        Dùng khi dịch thất bại (mất mạng, hết hạn mức) để pipeline thử lại
        cùng câu đó thay vì bỏ qua luôn.
        """
        self._last_text = ""


class Pipeline(threading.Thread):
    """Thread chạy vòng lặp chụp + OCR + dịch.

    region: dict {"left","top","width","height"} — vùng phụ đề trên màn hình.
    results: queue.Queue — nhận tuple ("subtitle", text_en, text_vi)
             hoặc ("error", message).
    """

    def __init__(self, region, results, poll_interval=0.5, debounce=0.3):
        super().__init__(daemon=True)
        self.region = dict(region)
        self.results = results
        self.poll_interval = poll_interval
        self.translator = Translator()
        self._stabilizer = TextStabilizer(debounce=debounce)
        self._stop = threading.Event()
        self._failures = 0

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                image = capture_region(self.region)
                text = ocr_image(image)
            except Exception as exc:  # noqa: BLE001 - báo lỗi ra GUI, không crash
                self.results.put(("error", f"Lỗi chụp/OCR: {exc}"))
                time.sleep(self.poll_interval)
                continue

            stable = self._stabilizer.observe(text, time.monotonic())
            if stable is not None:
                if stable:
                    try:
                        vi_text = self.translator.translate(stable)
                    except Exception as exc:  # noqa: BLE001
                        self.results.put(("error", f"Lỗi dịch: {exc}"))
                        vi_text = ""
                    if vi_text:
                        self._failures = 0
                        self.results.put(("subtitle", stable, vi_text))
                    else:
                        # Dịch thất bại (mất mạng / hết hạn mức): không bỏ
                        # câu này, chờ 5 giây rồi thử lại.
                        self._failures += 1
                        self._stabilizer.unmark()
                        self.results.put(
                            (
                                "error",
                                "Không dịch được (mạng hoặc hết hạn mức) — "
                                f"thử lại sau 5 giây (lần {self._failures}).",
                            )
                        )
                        time.sleep(5)
                else:
                    # Phụ đề đã biến mất -> xóa phụ đề trên màn hình
                    self.results.put(("subtitle", "", ""))
            time.sleep(self.poll_interval)

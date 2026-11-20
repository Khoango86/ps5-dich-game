"""Luồng chạy nền: chụp -> OCR -> chống lặp -> tra kho text -> dịch -> GUI.

- Chống lặp: chỉ dịch khi text OCR thay đổi so với câu đã dịch.
- Debounce: text phải ổn định (không đổi) ít nhất `debounce` giây mới dịch,
  tránh dịch những khung hình đang chuyển cảnh hoặc OCR chưa ổn định.
- Tra kho text: nếu text OCR khớp với một câu chuẩn trong kho text game
  (src/gamedb.py), app dịch CÂU CHUẨN đó thay vì text OCR thô — sửa được
  lỗi OCR trước khi dịch. Không có kho hoặc không khớp thì dịch trực tiếp
  như cũ.
- Cache dịch: câu đã khớp kho thì kiểm tra bảng translations trước — đã
  dịch rồi thì dùng ngay không gọi dịch vụ; chưa có thì dịch rồi lưu vào
  cache để lần sau dùng. Chỉ cache câu chuẩn đã khớp kho, không cache
  text OCR thô chưa khớp.
- Khi phụ đề biến mất (OCR ra ""), gửi tín hiệu xóa phụ đề.
"""

import threading
import time

from .capture import capture_region
from .gamedb import load as load_gamedb
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
    results: queue.Queue — nhận tuple ("subtitle", text_en, text_vi, meta)
             hoặc ("error", message). meta là dict thông tin khớp kho
             (category/group/hash/match) hoặc None nếu không khớp kho.
    gamedb: GameDB đã mở sẵn (GUI truyền vào để dùng chung một kết nối),
            hoặc None để tự mở kho mặc định (data/gta6.db). Không có kho
            thì gamedb là None và pipeline dịch trực tiếp như cũ.
    """

    def __init__(self, region, results, poll_interval=0.5, debounce=0.3,
                 gamedb=None):
        super().__init__(daemon=True)
        self.region = dict(region)
        self.results = results
        self.poll_interval = poll_interval
        self.translator = Translator()
        self._stabilizer = TextStabilizer(debounce=debounce)
        # Đặt tên _stop_event (không phải _stop) vì Thread đã có sẵn
        # phương thức nội bộ _stop() — đặt trùng tên sẽ làm join() lỗi.
        self._stop_event = threading.Event()
        self._failures = 0
        if gamedb is None:
            gamedb = load_gamedb()
        # Chỉ giữ kho khi mở được file DB, còn không thì dịch trực tiếp.
        self.gamedb = gamedb if gamedb.available else None

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
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
                    # Tra kho text trước khi dịch: nếu khớp thì dịch câu
                    # chuẩn trong kho (sạch lỗi OCR) thay vì text OCR thô.
                    to_translate = stable
                    match_meta = None
                    if self.gamedb is not None:
                        try:
                            found = self.gamedb.lookup(stable)
                        except Exception:  # noqa: BLE001 - kho lỗi thì
                            # bỏ qua, dịch trực tiếp như cũ
                            found = None
                        if found is not None:
                            to_translate, match_meta = found
                    vi_text = ""
                    if match_meta is not None:
                        # Câu đã khớp kho: kiểm tra cache dịch trước —
                        # đã dịch rồi thì dùng ngay, không gọi dịch vụ.
                        try:
                            vi_text = (
                                self.gamedb.get_translation(to_translate)
                                or ""
                            )
                        except Exception:  # noqa: BLE001 - cache lỗi thì
                            # bỏ qua, dịch trực tiếp như cũ
                            vi_text = ""
                        if vi_text:
                            match_meta = dict(match_meta, cached=True)
                    if not vi_text:
                        try:
                            vi_text = self.translator.translate(to_translate)
                        except Exception as exc:  # noqa: BLE001
                            self.results.put(("error", f"Lỗi dịch: {exc}"))
                            vi_text = ""
                        # Chỉ cache bản dịch của câu chuẩn đã khớp kho —
                        # không cache text OCR thô chưa khớp.
                        if vi_text and match_meta is not None:
                            try:
                                self.gamedb.save_translation(
                                    to_translate, vi_text, "live-mt"
                                )
                            except Exception:  # noqa: BLE001 - lưu cache
                                # lỗi thì bỏ qua, bản dịch vẫn hiện
                                pass
                    if vi_text:
                        self._failures = 0
                        self.results.put(
                            ("subtitle", to_translate, vi_text, match_meta)
                        )
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
                    self.results.put(("subtitle", "", "", None))
            time.sleep(self.poll_interval)

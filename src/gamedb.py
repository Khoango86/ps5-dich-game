"""Kho text game (SQLite): tra cứu câu chuẩn của game trước khi dịch.

Vấn đề: OCR đọc phụ đề game thường sai vài ký tự (thiếu dấu câu, dính chữ,
nhầm chữ). Nếu dịch thẳng text OCR sai thì bản dịch cũng sai theo.

Giải pháp: kho text chứa toàn bộ câu thoại/phụ đề tiếng Anh gốc của game
(xây từ file TSV bằng tools/build_gamedb.py, lưu ở data/gta6.db). Trước khi
dịch, app tra cứu text OCR trong kho:
  1. Khớp chính xác sau khi chuẩn hóa (không phân biệt hoa/thường, dấu câu).
  2. Khớp "compact" (chỉ còn chữ+số, bỏ hết khoảng trắng/dấu câu) — chịu
     được lỗi OCR về khoảng trắng và dấu câu.
  3. Khớp chuỗi con (chỉ khi câu truy vấn đủ dài) — khi OCR chỉ đọc được
     một phần câu, hoặc câu game dài hơn phần hiện trên màn hình. Dùng
     phrase query trên bảng FTS5 (vài ms); nếu DB không có bảng FTS5 thì
     dùng LIKE dự phòng (chậm hơn).

Nếu khớp, app dịch CÂU CHUẨN trong kho thay vì text OCR thô, nên bản dịch
chính xác hơn (nhất là tên riêng). Nếu không có file DB hoặc không khớp,
app vẫn chạy bình thường bằng dịch trực tiếp (live MT) như cũ.

Cache dịch: mỗi câu khớp kho chỉ dịch 1 lần, bản dịch tiếng Việt được lưu
vào bảng `translations` trong cùng file DB (khóa là câu đã chuẩn hóa).
Lần sau gặp lại câu đó, app lấy bản dịch từ cache ngay, không gọi dịch
vụ nữa — vừa nhanh vừa đỡ tốn hạn mức dịch. Chơi càng lâu, kho dịch
Việt của game càng đầy. CHỈ cache bản dịch của câu chuẩn đã khớp kho;
không bao giờ cache bản dịch của text OCR thô chưa khớp (tránh đưa lỗi
OCR vào kho dịch).

Lưu ý bản quyền: file DB chứa text của game (tài sản của Rockstar/Take-Two),
người dùng tự tải và tự build trên máy mình — DB KHÔNG được commit vào repo.
"""

import os
import re
import sqlite3
import string
import sys
import unicodedata
from datetime import datetime, timezone

# Dấu ngoặc/dấu gạch "cong" (kiểu in ấn) -> dạng thẳng thường gặp trong OCR.
_QUOTE_MAP = str.maketrans(
    {
        "\u2018": "'",  # ‘
        "\u2019": "'",  # ’
        "\u201c": '"',  # “
        "\u201d": '"',  # ”
        "\u2013": "-",  # –
        "\u2014": "-",  # —
        "\u2212": "-",  # −
    }
)
_PUNCT_RE = re.compile("[" + re.escape(string.punctuation) + "]")

# Tra cứu chuỗi con chỉ chạy khi câu truy vấn (đã chuẩn hóa) đủ dài,
# tránh khớp nhầm những câu ngắn như "yes" vào hàng nghìn câu khác.
MIN_SUBSTRING_LEN = 12
# Câu trong kho dài hơn câu truy vấn tối đa bao nhiêu ký tự thì vẫn xét
# cho khớp chuỗi con (giới hạn để truy vấn nhanh nhờ index theo độ dài).
SUBSTRING_MAX_EXTRA = 60


def normalize_text(text):
    """Chuẩn hóa text để so sánh: chữ thường, dấu câu thành khoảng trắng,
    gộp khoảng trắng thừa, thống nhất ngoặc kép/dấu gạch.

    Ví dụ: "Hey!  Eyes   open?" -> "hey eyes open"
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.translate(_QUOTE_MAP)
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def compact_text(text):
    """Chỉ giữ chữ và số, chữ thường, bỏ hết khoảng trắng/dấu câu.

    Chịu được lỗi OCR về khoảng trắng và dấu câu.
    Ví dụ: "Don't  be late!" -> "dontbelate"
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return "".join(ch for ch in text.lower() if ch.isalnum())


def default_db_path():
    """Đường dẫn mặc định tới file DB kho text.

    Thứ tự: biến môi trường PS5_GAME_DB -> thư mục data/ cạnh file .exe
    (bản đóng gói) -> thư mục data/ ở gốc dự án (chạy từ code nguồn).
    """
    env = os.environ.get("PS5_GAME_DB")
    if env:
        return env
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        frozen_path = os.path.join(exe_dir, "data", "gta6.db")
        if os.path.isfile(frozen_path):
            return frozen_path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "data", "gta6.db")


# Bảng cache dịch: câu chuẩn đã dịch 1 lần thì lưu lại, lần sau dùng ngay.
# build_gamedb.py tạo bảng này (rỗng) khi build DB; load() cũng chạy
# CREATE TABLE IF NOT EXISTS để DB build từ trước vẫn có bảng này.
TRANSLATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS translations (
    norm TEXT PRIMARY KEY,
    vi TEXT NOT NULL,
    source TEXT,
    updated_at TEXT
)
"""


class GameDB:
    """Tra cứu câu chuẩn trong kho text game + cache bản dịch tiếng Việt.

    Nếu file DB không tồn tại hoặc lỗi, `available` là False và `lookup`
    luôn trả None — app vẫn chạy bình thường bằng dịch trực tiếp.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or default_db_path()
        self._conn = None
        self._count = 0
        self._has_fts = False
        # _writable: ghi được vào DB không (để lưu cache dịch). Nếu file
        # DB nằm ở chỗ chỉ đọc thì tra cứu vẫn chạy, chỉ không lưu cache.
        self._writable = False
        if self.db_path and os.path.isfile(self.db_path):
            try:
                # Mở đọc-ghi (không phải read-only) để lưu được cache dịch.
                self._conn = sqlite3.connect(
                    self.db_path, check_same_thread=False
                )
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM entries"
                ).fetchone()
                self._count = row[0] if row else 0
                fts = self._conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='entries_fts'"
                ).fetchone()
                self._has_fts = fts is not None
                try:
                    self._conn.execute(TRANSLATIONS_SCHEMA)
                    self._conn.commit()
                    self._writable = True
                except sqlite3.Error:
                    self._writable = False
            except sqlite3.Error:
                self._conn = None
                self._count = 0
                self._has_fts = False
                self._writable = False

    @property
    def available(self):
        """True nếu đã mở được file DB."""
        return self._conn is not None

    @property
    def row_count(self):
        """Số dòng trong kho (0 nếu chưa mở được DB)."""
        return self._count

    @property
    def translation_count(self):
        """Số câu đã có bản dịch trong cache (0 nếu chưa mở được DB)."""
        if self._conn is None:
            return 0
        try:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM translations"
            ).fetchone()
            return row[0] if row else 0
        except sqlite3.Error:
            return 0

    def get_translation(self, text):
        """Lấy bản dịch tiếng Việt đã lưu cho một câu chuẩn.

        Nhận câu gốc tiếng Anh (hoặc câu đã chuẩn hóa — hàm tự chuẩn hóa
        lại, kết quả như nhau). Trả về bản dịch, hoặc None nếu chưa có.
        """
        if self._conn is None:
            return None
        norm = normalize_text(text)
        if not norm:
            return None
        try:
            row = self._conn.execute(
                "SELECT vi FROM translations WHERE norm = ?", (norm,)
            ).fetchone()
        except sqlite3.Error:
            return None
        return row[0] if row else None

    def save_translation(self, text, vi, source="live-mt"):
        """Lưu bản dịch tiếng Việt cho một câu chuẩn vào cache.

        CHỈ gọi với câu chuẩn đã khớp kho — không bao giờ lưu bản dịch
        của text OCR thô chưa khớp (tránh đưa lỗi OCR vào kho dịch).
        Trả về True nếu lưu được, False nếu không (DB chỉ đọc / lỗi).
        """
        if self._conn is None or not self._writable:
            return False
        norm = normalize_text(text)
        vi = (vi or "").strip()
        if not norm or not vi:
            return False
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO translations "
                "(norm, vi, source, updated_at) VALUES (?, ?, ?, ?)",
                (norm, vi, source or "",
                 datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            self._conn.commit()
            return True
        except sqlite3.Error:
            return False

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _row_to_result(self, row, match_type):
        en, category, group, hash_, entry_id, ukey = row
        meta = {
            "category": category or "",
            "group": group or "",
            "hash": hash_ or "",
            "id": entry_id or "",
            "ukey": ukey or "",
            "match": match_type,
        }
        return en, meta

    def lookup(self, text):
        """Tra cứu text OCR trong kho.

        Trả về (câu_chuẩn_tiếng_Anh, meta) hoặc None nếu không khớp.
        meta: {"category", "group", "hash", "id", "ukey", "match"}.
        Thứ tự khớp: norm chính xác -> compact -> chuỗi con.
        """
        if self._conn is None:
            return None
        norm = normalize_text(text)
        if not norm:
            return None

        # 1. Khớp chính xác sau chuẩn hóa (dùng index, rất nhanh).
        row = self._conn.execute(
            "SELECT en, category, group_name, hash, id, ukey "
            "FROM entries WHERE norm = ? LIMIT 1",
            (norm,),
        ).fetchone()
        if row:
            return self._row_to_result(row, "norm")

        # 2. Khớp compact (bỏ khoảng trắng/dấu câu — chịu lỗi OCR).
        compact = compact_text(text)
        if compact:
            row = self._conn.execute(
                "SELECT en, category, group_name, hash, id, ukey "
                "FROM entries WHERE compact = ? LIMIT 1",
                (compact,),
            ).fetchone()
            if row:
                return self._row_to_result(row, "compact")

        # 3. Khớp chuỗi con: câu truy vấn nằm trong một câu dài hơn của kho.
        # Chỉ chạy khi câu đủ dài. Ưu tiên phrase query trên bảng FTS5
        # (vài ms); nếu DB không có bảng FTS5 thì dùng LIKE dự phòng.
        if len(norm) >= MIN_SUBSTRING_LEN:
            if self._has_fts:
                result = self._lookup_substring_fts(norm)
            else:
                result = self._lookup_substring_like(norm)
            if result is not None:
                return result

        return None

    def _lookup_substring_fts(self, norm):
        """Khớp chuỗi con bằng FTS5 phrase query.

        Thử cụm từ đầy đủ trước; nếu không khớp và câu đủ dài thì thử 2
        nửa câu (chịu được 1 từ bị OCR sai ở giữa). Lấy câu ngắn nhất
        chứa cụm từ (khớp sát nghĩa nhất).
        """
        words = [w for w in norm.split(" ") if w]
        if len(words) < 2:
            return None
        phrases = [" ".join(words)]
        if len(words) >= 6:
            half = len(words) // 2
            phrases.append(" ".join(words[:half]))
            phrases.append(" ".join(words[half:]))
        best = None
        for phrase in phrases:
            # Từ trong norm chỉ còn chữ/số nên an toàn cho cú pháp FTS5,
            # vẫn lọc lại cho chắc (bỏ mọi ký tự không phải chữ/số).
            safe = " ".join(
                "".join(ch for ch in w if ch.isalnum()) for w in phrase.split(" ")
            )
            safe = " ".join(safe.split())
            if len(safe) < MIN_SUBSTRING_LEN:
                continue
            try:
                rows = self._conn.execute(
                    "SELECT e.en, e.category, e.group_name, e.hash, e.id, "
                    "e.ukey, length(e.norm) AS n FROM entries_fts AS f "
                    "JOIN entries AS e ON e.rowid = f.rowid "
                    "WHERE f.norm MATCH ? ORDER BY n LIMIT 3",
                    ('"{}"'.format(safe),),
                ).fetchall()
            except sqlite3.Error:
                return None
            if rows:
                candidate = rows[0]
                if best is None or candidate[6] < best[6]:
                    best = candidate
        if best is not None:
            return self._row_to_result(best[:6], "substring")
        return None

    def _lookup_substring_like(self, norm):
        """Khớp chuỗi con bằng LIKE (dự phòng khi DB không có bảng FTS5).

        Giới hạn độ dài câu trong kho để dùng được index theo độ dài
        (tránh quét toàn bộ bảng), lấy câu ngắn nhất chứa nó.
        """
        escaped = norm.replace("\\", "\\\\").replace("%", "\\%").replace(
            "_", "\\_"
        )
        rows = self._conn.execute(
            "SELECT en, category, group_name, hash, id, ukey, "
            "length(norm) AS n FROM entries "
            "WHERE length(norm) BETWEEN ? AND ? "
            "AND norm LIKE ? ESCAPE '\\' "
            "ORDER BY n LIMIT 3",
            (len(norm), len(norm) + SUBSTRING_MAX_EXTRA,
             "%{}%".format(escaped)),
        ).fetchall()
        if rows:
            # rows có thêm cột length(norm) ở cuối -> chỉ lấy 6 cột đầu.
            return self._row_to_result(rows[0][:6], "substring")
        return None


def load(db_path=None):
    """Mở kho text game. Không raise lỗi khi file DB vắng — trả về GameDB
    với available=False để app vẫn chạy bằng dịch trực tiếp."""
    try:
        return GameDB(db_path=db_path)
    except Exception:  # noqa: BLE001 - kho text là tính năng phụ, không
        # được làm app crash
        db = GameDB.__new__(GameDB)
        db.db_path = db_path or default_db_path()
        db._conn = None
        db._count = 0
        db._has_fts = False
        db._writable = False
        return db

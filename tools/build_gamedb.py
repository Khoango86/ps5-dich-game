"""Build kho text game (SQLite) từ file TSV dump text tiếng Anh của game.

Cách dùng (chạy từ thư mục gốc dự án):

    python tools/build_gamedb.py data-src/all_rows.tsv
    python tools/build_gamedb.py data-src/all_rows.tsv --out data/gta6.db

Định dạng TSV hỗ trợ:
  - all_rows.tsv (gộp): cột id, pack, table, idx, hash, category, group,
    keep, ukey, en.
  - raw_*.tsv (thô): cột table, table_offset, idx, hash, text.
    (script tự nhận diện theo tên cột; với file thô thì category/group
    để trống, group lấy tên bảng.)

Kết quả: file SQLite `data/gta6.db`, bảng entries:
  id, ukey, hash, category, group_name, en, norm, compact
  (norm/compact xem src/gamedb.py — chuẩn hóa để tra cứu chịu lỗi OCR).
  Ngoài ra còn có bảng translations (rỗng lúc build): app lưu bản dịch
  tiếng Việt vào đó khi chơi, mỗi câu chuẩn chỉ dịch 1 lần rồi dùng lại.

Script chạy lại được nhiều lần (build ra file tạm rồi đổi tên đè lên file
cũ). Các dòng text rỗng bị bỏ; các dòng trùng nhau sau chuẩn hóa chỉ giữ
dòng đầu tiên.

Lưu ý bản quyền: file TSV và file .db chứa text của game (tài sản của
Rockstar/Take-Two) — chỉ dùng trên máy cá nhân để tra cứu khi dịch, KHÔNG
commit vào repo (đã có trong .gitignore).
"""

import argparse
import csv
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src.gamedb import compact_text, normalize_text  # noqa: E402

BATCH_SIZE = 5000

SCHEMA = """
CREATE TABLE entries (
    id TEXT PRIMARY KEY,
    ukey TEXT,
    hash TEXT,
    category TEXT,
    group_name TEXT,
    en TEXT NOT NULL,
    norm TEXT NOT NULL,
    compact TEXT NOT NULL
);

-- Cache dịch tiếng Việt: tạo rỗng lúc build, app ghi dần khi chơi
-- (mỗi câu chuẩn chỉ dịch 1 lần rồi dùng lại).
CREATE TABLE translations (
    norm TEXT PRIMARY KEY,
    vi TEXT NOT NULL,
    source TEXT,
    updated_at TEXT
);
"""

INDEXES = [
    "CREATE INDEX idx_entries_norm ON entries(norm)",
    "CREATE INDEX idx_entries_compact ON entries(compact)",
    # Index theo độ dài để tra cứu chuỗi con (dự phòng khi không có FTS5)
    # không phải quét toàn bảng.
    "CREATE INDEX idx_entries_norm_len ON entries(length(norm))",
]

# Bảng FTS5 (external content — chỉ lưu index, không nhân đôi text) để
# tra cứu chuỗi con bằng phrase query thay vì LIKE '%...%' quét toàn bảng
# (LIKE mất 400-600ms trên DB đầy, phrase query chỉ vài ms).
FTS5_CREATE = (
    "CREATE VIRTUAL TABLE entries_fts USING fts5("
    "norm, content='entries', content_rowid='rowid', "
    "tokenize='unicode61')"
)


def iter_rows(tsv_path):
    """Đọc TSV, yield dict đã chuẩn hóa cột (id, ukey, hash, category,
    group_name, en). Tự nhận diện định dạng gộp hay thô."""
    with open(tsv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = set(reader.fieldnames or [])
        if "en" in fields:
            mode = "consolidated"
        elif "text" in fields:
            mode = "raw"
        else:
            raise ValueError(
                "Không nhận diện được định dạng TSV (thiếu cột 'en' "
                "hoặc 'text'). Cột có: {}".format(
                    ", ".join(reader.fieldnames or [])
                )
            )
        for row in reader:
            if mode == "consolidated":
                yield {
                    "id": row.get("id") or "",
                    "ukey": row.get("ukey") or "",
                    "hash": row.get("hash") or "",
                    "category": row.get("category") or "",
                    "group_name": row.get("group") or "",
                    "en": row.get("en") or "",
                }
            else:
                table = row.get("table") or ""
                idx = row.get("idx") or ""
                yield {
                    "id": "{}_{}".format(table, idx),
                    "ukey": "",
                    "hash": row.get("hash") or "",
                    "category": "",
                    "group_name": table,
                    "en": row.get("text") or "",
                }


def build(tsv_path, out_path):
    """Build DB từ TSV. Trả về dict thống kê."""
    started = time.monotonic()
    tmp_path = out_path + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    read = 0
    skipped_empty = 0
    skipped_dup = 0
    inserted = 0
    seen_norms = set()

    conn = sqlite3.connect(tmp_path)
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -64000")
        conn.executescript(SCHEMA)

        batch = []
        for row in iter_rows(tsv_path):
            read += 1
            en = (row["en"] or "").strip()
            if not en:
                skipped_empty += 1
                continue
            norm = normalize_text(en)
            if not norm:
                skipped_empty += 1
                continue
            if norm in seen_norms:
                skipped_dup += 1
                continue
            seen_norms.add(norm)
            batch.append(
                (
                    row["id"],
                    row["ukey"],
                    row["hash"],
                    row["category"],
                    row["group_name"],
                    en,
                    norm,
                    compact_text(en),
                )
            )
            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO entries "
                    "(id, ukey, hash, category, group_name, en, norm, "
                    "compact) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                inserted += len(batch)
                batch.clear()
        if batch:
            conn.executemany(
                "INSERT OR IGNORE INTO entries "
                "(id, ukey, hash, category, group_name, en, norm, "
                "compact) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            inserted += len(batch)
        conn.commit()
        for stmt in INDEXES:
            conn.execute(stmt)
        # FTS5 cho tra cứu chuỗi con nhanh. Nếu SQLite không có FTS5 thì
        # bỏ qua (app sẽ dùng LIKE dự phòng, chậm hơn nhưng vẫn chạy).
        fts_built = False
        try:
            conn.execute(FTS5_CREATE)
            conn.execute(
                "INSERT INTO entries_fts(rowid, norm) "
                "SELECT rowid, norm FROM entries"
            )
            conn.execute("INSERT INTO entries_fts(entries_fts) "
                         "VALUES('optimize')")
            fts_built = True
        except sqlite3.Error as exc:
            print("  (cảnh báo: không tạo được bảng FTS5 ({}); tra cứu "
                  "chuỗi con sẽ dùng LIKE chậm hơn.)".format(exc))
        conn.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()

    os.replace(tmp_path, out_path)
    elapsed = time.monotonic() - started
    size = os.path.getsize(out_path)
    return {
        "read": read,
        "skipped_empty": skipped_empty,
        "skipped_dup": skipped_dup,
        "inserted": inserted,
        "fts_built": fts_built,
        "size_bytes": size,
        "elapsed_sec": elapsed,
        "out_path": out_path,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build kho text game (SQLite) từ file TSV."
    )
    parser.add_argument(
        "tsv",
        nargs="?",
        default=os.path.join(ROOT, "data-src", "all_rows.tsv"),
        help="Đường dẫn file TSV (mặc định: data-src/all_rows.tsv)",
    )
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT, "data", "gta6.db"),
        help="Đường dẫn file DB đầu ra (mặc định: data/gta6.db)",
    )
    args = parser.parse_args(argv)

    if not os.path.isfile(args.tsv):
        print("LỖI: không tìm thấy file TSV: {}".format(args.tsv))
        print("Hãy tải file TSV về data-src/ trước (xem README, mục "
              "'Kho text game (GTA 6)').")
        return 1

    print("Build kho text từ: {}".format(args.tsv))
    stats = build(args.tsv, args.out)
    print("  Đọc: {:,} dòng".format(stats["read"]))
    print("  Bỏ (text rỗng): {:,}".format(stats["skipped_empty"]))
    print("  Bỏ (trùng sau chuẩn hóa): {:,}".format(stats["skipped_dup"]))
    print("  Ghi vào DB: {:,} dòng".format(stats["inserted"]))
    print("  Bảng FTS5 (tra cứu chuỗi con nhanh): {}".format(
        "có" if stats["fts_built"] else "KHÔNG (dùng LIKE dự phòng)"))
    print("  File DB: {} ({:.1f} MB)".format(
        stats["out_path"], stats["size_bytes"] / (1024 * 1024)))
    print("  Thời gian: {:.1f} giây".format(stats["elapsed_sec"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tạo ảnh test giả lập màn hình game có phụ đề tiếng Anh.

Ảnh 1280x720: nền tối dạng cảnh game, vài chi tiết HUD (thanh máu, minimap,
mục tiêu) làm nhiễu, và dòng phụ đề chữ trắng đậm ở cuối màn hình — giống
cách phụ đề hiện trong game thật.
"""

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts", "arialbd.ttf"),
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts", "calibrib.ttf"),
]
FONT_REG_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts", "arial.ttf"),
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts", "calibri.ttf"),
]

SUBTITLE_1 = [
    "We need to get out of Vice City before dawn.",
    "Follow me, and stay quiet.",
]
SUBTITLE_2 = [
    "The shipment arrives at midnight.",
    "Don't be late.",
]

# Vùng phụ đề trong ảnh test (để test crop đúng vùng OCR đọc)
SUBTITLE_REGION = (140, 560, 1140, 660)  # left, top, right, bottom


def _font(candidates, size):
    """Thử lần lượt các đường dẫn font (Linux rồi Windows); nếu không có
    font nào thì dùng font mặc định của Pillow (rất nhỏ — chỉ là cứu cánh,
    OCR có thể đọc kém)."""
    if isinstance(candidates, str):
        candidates = [candidates]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_game_image(subtitle_lines, out_path):
    img = Image.new("RGB", (1280, 720), (18, 24, 38))
    draw = ImageDraw.Draw(img, "RGBA")

    # Nền dạng cảnh đêm: dải sáng ngang (đường chân trời) + vài khối nhà
    for y in range(0, 420, 4):
        shade = 18 + int(30 * (y / 420))
        draw.line([(0, y), (1280, y)], fill=(shade, shade + 8, shade + 22))
    for x0, w, h in [(60, 150, 260), (260, 110, 200), (430, 190, 300),
                     (700, 130, 230), (880, 170, 280), (1100, 120, 210)]:
        draw.rectangle([x0, 420 - h, x0 + w, 420], fill=(28, 32, 48))
        for wy in range(420 - h + 20, 400, 45):
            for wx in range(x0 + 15, x0 + w - 15, 35):
                draw.rectangle([wx, wy, wx + 16, wy + 22],
                               fill=(255, 214, 110, 220))
    # Mặt đường
    draw.rectangle([0, 420, 1280, 720], fill=(30, 30, 34))
    for x in range(0, 1280, 120):
        draw.rectangle([x, 560, x + 60, 568], fill=(220, 200, 90))

    # HUD: thanh máu góc trái trên
    draw.rectangle([30, 30, 330, 56], fill=(0, 0, 0, 160))
    draw.rectangle([36, 36, 324, 50], fill=(60, 60, 60))
    draw.rectangle([36, 36, 240, 50], fill=(90, 200, 90))
    # HUD: minimap góc phải trên
    draw.ellipse([1130, 30, 1250, 150], fill=(10, 40, 20, 200),
                 outline=(255, 255, 255), width=2)
    draw.ellipse([1175, 75, 1205, 105], fill=(255, 80, 80))
    # HUD: mục tiêu góc trái
    font_small = _font(FONT_REG_CANDIDATES, 20)
    draw.text((30, 70), "OBJECTIVE: Reach the hideout", font=font_small,
              fill=(255, 255, 255))

    # Thanh phụ đề: nền đen mờ + chữ trắng đậm có bóng
    draw.rectangle([100, 545, 1180, 675], fill=(0, 0, 0, 170))
    font_sub = _font(FONT_BOLD_CANDIDATES, 30)
    y = 560
    for line in subtitle_lines:
        tw = draw.textlength(line, font=font_sub)
        x = (1280 - tw) // 2
        draw.text((x + 2, y + 2), line, font=font_sub, fill=(0, 0, 0))
        draw.text((x, y), line, font=font_sub, fill=(255, 255, 255))
        y += 42

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    return out_path


def main():
    p1 = make_game_image(SUBTITLE_1, os.path.join(ASSETS, "game_subtitle_1.png"))
    p2 = make_game_image(SUBTITLE_2, os.path.join(ASSETS, "game_subtitle_2.png"))
    print(f"Đã tạo: {p1}")
    print(f"Đã tạo: {p2}")
    print(f"Vùng phụ đề: {SUBTITLE_REGION}")


if __name__ == "__main__":
    main()

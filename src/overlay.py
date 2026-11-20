"""Cửa sổ phụ đề trong suốt, luôn nổi trên cùng, kéo thả được bằng chuột."""

import tkinter as tk


class SubtitleOverlay:
    """Thanh phụ đề tiếng Việt nổi trên màn hình.

    Nền đen mờ, chữ trắng đậm, căn giữa gần đáy màn hình. Người dùng có thể
    kéo thanh phụ đề tới vị trí khác bằng chuột.
    """

    def __init__(self, root, font_size=20):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)  # không viền, không tiêu đề
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.win.attributes("-alpha", 0.88)
        except tk.TclError:
            pass
        self.label = tk.Label(
            self.win,
            text="",
            font=("Segoe UI", font_size, "bold"),
            fg="white",
            bg="black",
            wraplength=1000,
            justify="center",
            padx=18,
            pady=10,
        )
        self.label.pack()
        self._drag = {"x": 0, "y": 0}
        self.label.bind("<Button-1>", self._drag_start)
        self.label.bind("<B1-Motion>", self._drag_move)
        self.win.withdraw()  # ẩn cho tới khi có phụ đề đầu tiên
        self._placed = False

    def _drag_start(self, event):
        self._drag = {"x": event.x, "y": event.y}

    def _drag_move(self, event):
        x = self.win.winfo_x() + event.x - self._drag["x"]
        y = self.win.winfo_y() + event.y - self._drag["y"]
        self.win.geometry(f"+{x}+{y}")

    def _place_bottom_center(self):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w = self.win.winfo_width()
        self.win.geometry(f"+{(sw - w) // 2}+{sh - 200}")

    def show(self, text):
        """Hiện phụ đề. text rỗng -> ẩn cửa sổ."""
        if not text:
            self.win.withdraw()
            return
        self.label.config(text=text)
        self.win.deiconify()
        if not self._placed:
            self._place_bottom_center()
            self._placed = True
        else:
            # Căn giữa lại theo chiều ngang (giữ nguyên vị trí dọc người dùng đã kéo)
            self.win.update_idletasks()
            sw = self.win.winfo_screenwidth()
            w = self.win.winfo_width()
            self.win.geometry(f"+{(sw - w) // 2}+{self.win.winfo_y()}")

    def hide(self):
        self.win.withdraw()

    def set_font_size(self, size):
        try:
            size = int(size)
        except (TypeError, ValueError):
            return
        size = max(12, min(48, size))
        self.label.config(font=("Segoe UI", size, "bold"))

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass

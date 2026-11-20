"""Bảng điều khiển chính: chọn vùng, bắt đầu/dừng, xem gốc + bản dịch."""

import queue
import tkinter as tk
from tkinter import messagebox, ttk

from .overlay import SubtitleOverlay
from .pipeline import Pipeline
from .region_picker import pick_region

DEFAULT_REGION = {"left": 100, "top": 800, "width": 800, "height": 120}


def format_region(region):
    return (
        f"X={region['left']}, Y={region['top']}, "
        f"Rộng={region['width']}, Cao={region['height']}"
    )


class ControlPanel:
    def __init__(self, root, tesseract_path=None):
        self.root = root
        self.root.title("PS5 Dịch Game — Phụ đề tiếng Việt trực tiếp")
        self.root.geometry("560x600")
        self.root.resizable(False, False)
        self.tesseract_path = tesseract_path

        # Vùng mặc định: dải ngang gần đáy màn hình (tính theo kích thước
        # màn hình thật để không bị lệch trên màn hình nhỏ).
        try:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            self.region = {
                "left": int(sw * 0.10),
                "top": int(sh * 0.78),
                "width": int(sw * 0.80),
                "height": int(sh * 0.12),
            }
        except tk.TclError:
            self.region = dict(DEFAULT_REGION)
        self.results = queue.Queue()
        self.pipeline = None
        self.overlay = SubtitleOverlay(root)
        self.show_overlay = tk.BooleanVar(value=True)
        self.font_size = tk.IntVar(value=20)

        self._build_widgets()
        if tesseract_path is None:
            self._set_status(
                "⚠ Không tìm thấy Tesseract. Hãy cài Tesseract rồi mở lại app "
                "(xem README).",
                error=True,
            )
        else:
            self._set_status("Sẵn sàng. Hãy chọn vùng phụ đề rồi bấm Bắt đầu dịch.")
        self.root.after(200, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- Giao diện ----
    def _build_widgets(self):
        pad = {"padx": 10, "pady": 6}

        title = tk.Label(
            self.root,
            text="PS5 Dịch Game",
            font=("Segoe UI", 18, "bold"),
        )
        title.pack(**pad)

        hint = tk.Label(
            self.root,
            text="Mở app PS Remote Play trên laptop, rồi chọn vùng phụ đề\n"
            "(vùng chữ tiếng Anh dưới màn hình game) để app đọc và dịch.",
            font=("Segoe UI", 10),
            justify="center",
        )
        hint.pack(**pad)

        # Vùng phụ đề
        region_frame = ttk.LabelFrame(self.root, text="Vùng phụ đề")
        region_frame.pack(fill="x", **pad)
        self.region_label = tk.Label(region_frame, text=format_region(self.region))
        self.region_label.pack(side="left", padx=8, pady=6)
        pick_btn = ttk.Button(
            region_frame, text="Chọn vùng phụ đề…", command=self._on_pick_region
        )
        pick_btn.pack(side="right", padx=8, pady=6)

        # Điều khiển
        ctrl_frame = ttk.LabelFrame(self.root, text="Điều khiển")
        ctrl_frame.pack(fill="x", **pad)
        self.start_btn = ttk.Button(
            ctrl_frame, text="▶  Bắt đầu dịch", command=self._on_start
        )
        self.start_btn.pack(side="left", padx=8, pady=6)
        self.stop_btn = ttk.Button(
            ctrl_frame, text="⏹  Dừng", command=self._on_stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=4, pady=6)
        ttk.Label(ctrl_frame, text="Cỡ chữ:").pack(side="left", padx=(12, 2))
        size_spin = ttk.Spinbox(
            ctrl_frame,
            from_=12,
            to=48,
            width=4,
            textvariable=self.font_size,
            command=self._on_font_size,
        )
        size_spin.pack(side="left", padx=2, pady=6)
        overlay_check = ttk.Checkbutton(
            ctrl_frame,
            text="Hiện phụ đề",
            variable=self.show_overlay,
            command=self._on_toggle_overlay,
        )
        overlay_check.pack(side="left", padx=8, pady=6)

        # Text gốc
        orig_frame = ttk.LabelFrame(self.root, text="Tiếng Anh (gốc)")
        orig_frame.pack(fill="both", expand=True, **pad)
        self.orig_text = tk.Text(orig_frame, height=4, wrap="word", state="disabled")
        self.orig_text.pack(fill="both", expand=True, padx=6, pady=6)

        # Text dịch
        vi_frame = ttk.LabelFrame(self.root, text="Tiếng Việt (dịch)")
        vi_frame.pack(fill="both", expand=True, **pad)
        self.vi_text = tk.Text(vi_frame, height=4, wrap="word", state="disabled")
        self.vi_text.pack(fill="both", expand=True, padx=6, pady=6)

        # Trạng thái
        self.status_label = tk.Label(
            self.root, text="", font=("Segoe UI", 9), anchor="w", justify="left"
        )
        self.status_label.pack(fill="x", **pad)

    # ---- Xử lý sự kiện ----
    def _set_status(self, text, error=False):
        self.status_label.config(text=text, fg=("red" if error else "black"))

    def _set_text(self, widget, text):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _on_pick_region(self):
        if self.pipeline is not None:
            messagebox.showinfo(
                "Đang dịch", "Hãy bấm Dừng trước khi chọn lại vùng phụ đề."
            )
            return
        region = pick_region(self.root)
        if region:
            self.region = region
            self.region_label.config(text=format_region(region))
            self._set_status("Đã chọn vùng phụ đề mới.")

    def _on_start(self):
        if self.tesseract_path is None:
            messagebox.showerror(
                "Thiếu Tesseract",
                "Không tìm thấy Tesseract trên máy.\n"
                "Hãy cài Tesseract (xem README) rồi mở lại app.",
            )
            return
        if self.pipeline is not None:
            return
        self.pipeline = Pipeline(self.region, self.results)
        self.pipeline.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._set_status("Đang dịch… (đọc vùng phụ đề mỗi 0,5 giây)")

    def _on_stop(self):
        if self.pipeline is None:
            return
        self.pipeline.stop()
        self.pipeline = None
        self.overlay.hide()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._set_status("Đã dừng.")

    def _on_font_size(self):
        try:
            size = self.font_size.get()
        except (tk.TclError, ValueError):
            return  # người dùng đang gõ dở số không hợp lệ
        self.overlay.set_font_size(size)

    def _on_toggle_overlay(self):
        if not self.show_overlay.get():
            self.overlay.hide()
        else:
            current = self.vi_text.get("1.0", "end").strip()
            if current:
                self.overlay.show(current)

    def _poll_queue(self):
        try:
            while True:
                msg = self.results.get_nowait()
                if msg[0] == "subtitle":
                    _, en_text, vi_text = msg
                    self._set_text(self.orig_text, en_text)
                    self._set_text(self.vi_text, vi_text)
                    if self.show_overlay.get():
                        self.overlay.show(vi_text)
                    if en_text:
                        self._set_status("Đang dịch…")
                elif msg[0] == "error":
                    self._set_status(msg[1], error=True)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _on_close(self):
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
        self.overlay.destroy()
        self.root.destroy()


def run_app(tesseract_path=None):
    root = tk.Tk()
    ControlPanel(root, tesseract_path=tesseract_path)
    root.mainloop()

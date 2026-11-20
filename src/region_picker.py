"""Chọn vùng phụ đề bằng cách kéo chuột vẽ hình chữ nhật trên màn hình."""

import tkinter as tk


def pick_region(root):
    """Mở cửa sổ toàn màn hình cho người dùng kéo chuột chọn vùng.

    Trả về dict {"left","top","width","height"} (tọa độ màn hình),
    hoặc None nếu người dùng nhấn Esc / đóng cửa sổ mà không chọn.
    """
    result = {"region": None}
    top = tk.Toplevel(root)
    top.attributes("-fullscreen", True)
    try:
        top.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        top.attributes("-alpha", 0.35)
    except tk.TclError:
        pass
    top.configure(bg="gray")

    canvas = tk.Canvas(top, bg="gray", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    hint = tk.Label(
        top,
        text="Kéo chuột để chọn vùng phụ đề  •  Nhấn Esc để hủy",
        font=("Segoe UI", 16, "bold"),
        bg="yellow",
        fg="black",
        padx=12,
        pady=6,
    )
    hint.place(relx=0.5, y=20, anchor="n")

    state = {"x0": 0, "y0": 0, "rect": None}

    def on_press(event):
        state["x0"], state["y0"] = event.x, event.y
        if state["rect"] is not None:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=3
        )

    def on_drag(event):
        if state["rect"] is not None:
            canvas.coords(state["rect"], state["x0"], state["y0"], event.x, event.y)

    def on_release(event):
        x0, y0 = state["x0"], state["y0"]
        x1, y1 = event.x, event.y
        left, top_y = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        if width >= 20 and height >= 10:
            result["region"] = {
                "left": left,
                "top": top_y,
                "width": width,
                "height": height,
            }
        top.destroy()

    def on_escape(_event=None):
        top.destroy()

    canvas.bind("<Button-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    top.bind("<Escape>", on_escape)
    top.protocol("WM_DELETE_WINDOW", on_escape)
    top.focus_set()
    top.grab_set()
    root.wait_window(top)
    return result["region"]

#ui.py

from tkinter import ttk
import tkinter as tk
from browser_control import state

def show_splash():
    splash = tk.Tk()
    splash.overrideredirect(True)

    width, height = 500, 250
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)

    # Create border frame
    border_frame = tk.Frame(splash, bg="#1e1e1e")
    border_frame.pack(fill="both", expand=True, padx=6, pady=6)

    # Create inner content frame
    content_frame = tk.Frame(border_frame, bg="#1e1e1e")
    content_frame.pack(fill="both", expand=True)

    splash.geometry(f"{width}x{height}+{x}+{y}")
    splash.configure(bg="#1e1e1e")  # Set outer window background

    label = tk.Label(
        content_frame,  # Parent changed to content_frame
        text="Browser Control\nLoading...",
        font=("Segoe UI", 24, "bold"),
        bg="#1e1e1e",
        fg="white",
        justify="center"
    )
    label.pack(expand=True)

    return splash

def apply_theme():
    style = ttk.Style()
    style.theme_use("clam")

    # Notebook and tabs
    style.configure("TNotebook", background="#2b2b2b", borderwidth=0)
    style.configure("TNotebook.Tab", background="#1f1f1f", foreground="white", padding=[10, 5])
    style.map("TNotebook.Tab",
        background=[("selected", "#2b2b2b")],
        foreground=[("selected", "white")]
    )

    # General buttons
    style.configure("TButton", background="white", foreground="black", font=("Segoe UI", 10))
    style.map("TButton", background=[("active", "#e0e0e0")])

    # Update button
    style.configure("Update.TButton",
        background="#ffff88", foreground="black",
        bordercolor="#ccaa00", focusthickness=2,
        relief="solid", padding=6
    )
    style.map("Update.TButton",
        background=[("active", "#ffeb3b")],
        bordercolor=[("active", "#b38f00")]
    )

    # Danger button
    style.configure("Danger.TButton",
        background="#ff4444", foreground="white",
        bordercolor="#aa0000", focusthickness=2,
        relief="solid", padding=6
    )
    style.map("Danger.TButton",
        background=[("active", "#cc0000")],
        foreground=[("active", "white")]
    )

    # Global font
    state.root.option_add("*Font", ("Segoe UI", 10))
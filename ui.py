#ui.py

from tkinter import ttk
import tkinter as tk
import state

def show_splash():
    splash = tk.Tk()
    splash.overrideredirect(True)

    width, height = 500, 320
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)

    splash.geometry(f"{width}x{height}+{x}+{y}")
    splash.configure(bg="#1e1e1e")

    # Create border frame
    border_frame = tk.Frame(splash, bg="#1e1e1e")
    border_frame.pack(fill="both", expand=True, padx=6, pady=6)

    # Main container with vertical centering
    main_container = tk.Frame(border_frame, bg="#1e1e1e")
    main_container.pack(fill="both", expand=True)

    # Center content vertically using place
    content_frame = tk.Frame(main_container, bg="#1e1e1e")
    content_frame.place(relx=0.5, rely=0.45, anchor="center")

    # Main title
    title_label = tk.Label(
        content_frame,
        text="Browser Control",
        font=("Segoe UI", 28, "bold"),
        bg="#1e1e1e",
        fg="white",
        justify="center"
    )
    title_label.pack(pady=(0, 20))

    # Progress indicator
    progress_var = tk.StringVar(value="Initializing...")
    progress_label = tk.Label(
        content_frame,
        textvariable=progress_var,
        font=("Segoe UI", 11),
        bg="#1e1e1e",
        fg="#a0a0a0",
        justify="center"
    )
    progress_label.pack(pady=(0, 5))

    # Status message (for warnings/errors)
    status_var = tk.StringVar(value="")
    status_label = tk.Label(
        content_frame,
        textvariable=status_var,
        font=("Segoe UI", 9),
        bg="#1e1e1e",
        fg="#ffaa00",
        justify="center",
        wraplength=450
    )
    status_label.pack(pady=(0, 0))

    # Progress bar at the bottom (thin, pretty, #25adde color)
    progress_bar_container = tk.Frame(border_frame, bg="#1e1e1e", height=4)
    progress_bar_container.pack(side="bottom", fill="x", pady=(0, 10))
    
    # Background bar
    progress_bg = tk.Frame(progress_bar_container, bg="#3a3a3a", height=3)
    progress_bg.pack(fill="x", padx=20)
    
    # Actual progress bar (starts at 0 width)
    progress_bar = tk.Frame(progress_bg, bg="#25adde", height=3)
    progress_bar.place(x=0, y=0, relwidth=0, relheight=1)

    # Store variables on splash window for easy access
    splash.progress_var = progress_var
    splash.status_var = status_var
    splash.progress_bar = progress_bar
    splash.progress_bg = progress_bg

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
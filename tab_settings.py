import tkinter as tk
from tkinter import ttk
from browser_control import config, state
from browser_control.constants import DEPARTMENTS, ZOOM_OPTIONS
from browser_control.settings import save_settings, save_window_geometry
from browser_control.utils import flash_message
from browser_control.tab_tools import build_tools_tab

def build_settings_tab(parent):
    frame = tk.Frame(parent, bg="#2b2b2b", padx=10, pady=10)

    # Top message label
    msg_var = tk.StringVar(value="Change settings below")
    msg_lbl = tk.Label(frame, textvariable=msg_var, fg="white", bg="#2b2b2b")
    msg_lbl.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="ew")

    # Bound variables from config
    department_var = state.department_var
    zoom_var = state.zoom_var
    dark_var = tk.BooleanVar(value=config.cfg["darkmode"].lower() == "true")

    # Department dropdown
    tk.Label(frame, text="Location", bg="#2b2b2b", fg="white").grid(row=1, column=0, sticky="w", pady=5)
    dept_cb = ttk.Combobox(frame, textvariable=department_var, values=DEPARTMENTS, state="readonly")
    dept_cb.grid(row=1, column=1, sticky="ew", padx=5)

    # Zoom dropdown
    tk.Label(frame, text="Zoom %", bg="#2b2b2b", fg="white").grid(row=2, column=0, sticky="w", pady=5)
    zoom_cb = ttk.Combobox(frame, textvariable=zoom_var, values=ZOOM_OPTIONS, state="readonly")
    zoom_cb.grid(row=2, column=1, sticky="ew", padx=5)

    # Dark mode checkbox
    dark_cb = tk.Checkbutton(
        frame, text="Dark Mode (Decant)",
        variable=dark_var,
        bg="#2b2b2b", fg="white", selectcolor="#2b2b2b"
    )
    dark_cb.grid(row=3, column=0, columnspan=2, pady=5)

    # Auto-update cfg on change
    def update_cfg_from_controls(*_):
        try:
            if config.cfg["department"] != department_var.get():
                config.cfg["department"] = department_var.get()
                if state.tools_frame:
                    state.notebook.forget(state.tools_frame)
                    tools_tab = build_tools_tab()
                    state.notebook.add(tools_tab, text="Tools")

            config.cfg["zoom_var"] = zoom_var.get()
            config.cfg["darkmode"] = str(dark_var.get())
            save_settings()
            flash_message(msg_lbl, msg_var, "Settings updated", status='success')
        except Exception as e:
            flash_message(msg_lbl, msg_var, "Error saving settings", status='error')
            print(f"[ERROR] Save settings error: {e}")

    department_var.trace_add("write", update_cfg_from_controls)
    zoom_var.trace_add("write", update_cfg_from_controls)
    dark_var.trace_add("write", update_cfg_from_controls)

    def on_save_window_geometry():
        try:
            save_window_geometry()
            flash_message(msg_lbl, msg_var, "Position saved!", status='success')
        except:
            flash_message(msg_lbl, msg_var, "Error saving window position", status='error')

    ttk.Button(frame, text="Save position", command=on_save_window_geometry).grid(row=4, column=0, columnspan=2, pady=5)

    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)

    return frame
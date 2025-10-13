# tab_tools.py

import tkinter as tk
import state
from tools_slotstax import build_slotstax_tools
from tools_decant import build_decant_tools

def build_no_tools(parent, department):
    frame = tk.Frame(parent, bg="#2b2b2b", padx=10, pady=10)

    # Match the 3-column layout
    for i in range(3):
        frame.columnconfigure(i, weight=1)

    msg_var = tk.StringVar(value=f"No tools for {department}")
    msg_lbl = tk.Label(
        frame,
        textvariable=msg_var,
        bg="#2b2b2b",
        fg="white",
        anchor="center",   # center text in label
        justify="center",  # center multiline if any
    )
    msg_lbl.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

    return frame


def get_department_tools_frame(department: str, parent) -> tk.Frame | None:
    department = department.lower()

    if department.startswith("palletizingstation"):
        
        return build_slotstax_tools(parent)

    elif department.startswith("decant"):
        
        return build_decant_tools(parent)

    # Add more department handlers here

    return build_no_tools(parent, department)

def build_tools_tab():
    parent = state.notebook
    base_frame = tk.Frame(parent, bg="#2b2b2b", padx=10, pady=10)
    department = state.department_var.get().lower()
    
    # Load the correct tools sub-frame
    dept_tools = get_department_tools_frame(department, base_frame)

    if dept_tools:
        dept_tools.grid(row=1, column=0, columnspan=3, sticky="nsew")

    base_frame.rowconfigure(1, weight=1)
    state.tools_frame = base_frame
    return base_frame
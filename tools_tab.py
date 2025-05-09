import tkinter as tk
from tkinter import ttk
import pyodbc
from browser_control.launcher import select_on_scale 

def show_error_popup(title, message):
    popup = tk.Toplevel()
    popup.title(title)
    popup.configure(bg="#2b2b2b")
    popup.geometry("600x300")

    lbl = tk.Label(popup, text="Error Details:", bg="#2b2b2b", fg="white", font=("Segoe UI", 10, "bold"))
    lbl.pack(pady=(10, 0))

    text_box = tk.Text(popup, wrap="word", bg="white", fg="black", font=("Segoe UI", 10))
    text_box.insert("1.0", message)
    text_box.config(state="normal")
    text_box.pack(fill="both", expand=True, padx=10, pady=10)

    text_box.focus()
    text_box.tag_add("sel", "1.0", "end")  # auto-select all



def create_tools_tab(notebook, department_var):
    current_result_win = {"win": None}

    tools_frame = tk.Frame(notebook, bg="#2b2b2b", padx=10, pady=10)
    notebook.add(tools_frame, text="Tools")
    # make three columns for layout
    for c in range(3):
        tools_frame.columnconfigure(c, weight=1)

    # Error label var and label at top
    tools_error_var = tk.StringVar()
    tools_error_var.set("Pallet LP lookup by GTIN")
    error_lbl = tk.Label(
        tools_frame,
        textvariable=tools_error_var,
        bg="#2b2b2b",
        fg="white",
        font=("Segoe UI", 10)
    )
    error_lbl.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(5,15))

    # GTIN label and entry
    tk.Label(
        tools_frame,
        text="GTIN:",
        bg="#2b2b2b",
        fg="white",
        font=("Segoe UI", 10)
    ).grid(row=1, column=0, sticky="e")
    gtin_var = tk.StringVar()
    ttk.Entry(
        tools_frame,
        textvariable=gtin_var,
        font=("Segoe UI", 10)
    ).grid(row=1, column=1, columnspan=2, sticky="ew", padx=5)

    # Results placeholder row index
    RESULTS_ROW = 4
    # reserve space for results_frame
    results_frame = tk.Frame(tools_frame, bg="#2b2b2b")
    results_frame.grid(row=RESULTS_ROW, column=0, columnspan=3, sticky="nsew", pady=(10,0))
    tools_frame.rowconfigure(RESULTS_ROW, weight=1)

    def on_search():
        if current_result_win["win"] and current_result_win["win"].winfo_exists():
            current_result_win["win"].destroy()

        # Validate location
        loc = department_var.get()
        if not loc.startswith("DECANT.WS"):
            tools_error_var.set("Select a decant location from settings")
            return
        # Validate GTIN
        gtin = gtin_var.get().strip()
        if not gtin:
            tools_error_var.set("Enter value in GTIN field")
            return
        tools_error_var.set("")
        # Clear previous results
        for w in results_frame.winfo_children():
            w.destroy()

        import requests
        try:
            resp = requests.post("http://10.110.7.120:5000/lookup_lp_by_gtin", json={
                "gtin": gtin,
                "department": loc
            }, timeout=5)
            resp.raise_for_status()
            rows = resp.json()
        except requests.exceptions.ConnectionError:
            tools_error_var.set("Backend is not running")
            return
        except requests.exceptions.Timeout:
            tools_error_var.set("Backend request timed out")
            return
        except Exception as e:
            tools_error_var.set(f"Error: {e}")
            return
                
        if not rows:
            tools_error_var.set("No results")
            return

        # show results in new window
        result_win = tk.Toplevel(tools_frame)
        current_result_win["win"] = result_win
        result_win.title("GTIN Search Results")
        result_win.configure(bg="#2b2b2b")
        #result_win.minsize(400, 200)

        table = tk.Frame(result_win, bg="white", bd=1, relief="solid")
        table.pack(fill="both", expand=True, padx=10, pady=10)

        # headers
        headers = ("Location", "Item", "On hand qty", "To location", "License plate", "Select")
        for c, h in enumerate(headers):
            lbl = tk.Label(table, text=h, font=("Segoe UI", 10, "bold"),
                           bg="#2b2b2b", fg="white", bd=1, relief="solid", padx=10, pady=2)
            lbl.grid(row=0, column=c, sticky="nsew")
            table.columnconfigure(c, weight=1)

        # data rows
        for r, row in enumerate(rows, start=1):
            values = (
                row.get("LOCATION", ""),
                row.get("ITEM", ""),
                row.get("ON_HAND_QTY", ""),
                row.get("TO_LOC", ""),
                row.get("LOGISTICS_UNIT", "")
            )
            for c, val in enumerate(values):
                lbl = tk.Label(table, text=val, font=("Segoe UI", 10),
                            bg="#2b2b2b", fg="white", bd=1, relief="solid", padx=10, pady=2)
                lbl.grid(row=r, column=c, sticky="nsew")
            btn = ttk.Button(table, text="Select",
                            command=lambda rw=row, win=result_win: _on_select(rw, tools_error_var, gtin_var.get(), win))
            btn.grid(row=r, column=len(headers)-1, sticky="nsew")



    def _on_select(row, error_var, gtin, result_win):
        if row.get("UM_MATCH", 0):
            success, msg = select_on_scale(row["LOGISTICS_UNIT"], gtin)
        else:
            success, msg = select_on_scale(row["LOGISTICS_UNIT"], "")

        if not success:
            error_var.set(msg)
        # close the results window after a successful (or unsuccessful) select
        if result_win and result_win.winfo_exists():
            result_win.destroy()

    # Search button
    search_btn = ttk.Button(tools_frame, text="Search", command=on_search)
    search_btn.grid(row=3, column=0, columnspan=3, pady=(10,0))

    return tools_frame
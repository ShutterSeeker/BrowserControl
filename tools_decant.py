import tkinter as tk
from tkinter import ttk, messagebox
from chrome import select_on_scale
import requests
from constants import IP, PORT
import state
import traceback


def build_decant_tools(parent):
    frame = tk.Frame(parent, bg="#2b2b2b", padx=10, pady=10)

    # Status message label
    msg_var = tk.StringVar(value="Enter a gtin and click Search")
    msg_lbl = tk.Label(
        frame, textvariable=msg_var,
        bg="#2b2b2b", fg="white",
        wraplength=300
    )
    msg_lbl.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

    # GTIN entry
    loc = state.department_var.get()
    gtin_var = tk.StringVar()
    tk.Label(
        frame, text="GTIN:",
        bg="#2b2b2b", fg="white",
    ).grid(row=1, column=0, sticky="e", pady=5)
    gtin_entry = ttk.Entry(
        frame, textvariable=gtin_var,
    )
    gtin_entry.grid(row=1, column=1, sticky="ew", padx=(0,5))
    
    # Search button
    def on_search():
        gtin = gtin_var.get().strip()
        # Clear previous results
        for w in results_frame.winfo_children():
            w.destroy()
        if not gtin:
            msg_var.set("Please enter a GTIN.")
            return

        msg_var.set("Searching...")
        try:
            resp = requests.post(
                f"http://{IP}:{PORT}/lookup_lp_by_gtin",
                json={"gtin": gtin, "department": loc},
                timeout=5
            )
            resp.raise_for_status()
            rows = resp.json()

        except Exception as e:
            msg_var.set(f"Error: {e}")
            return

        if not rows:
            msg_var.set("No results found.")
            return

        if len(rows) == 1:
            msg_var.set("1 LP found")
        else:
            msg_var.set(f"{len(rows)} LPs found")

        # Close any existing results window before opening a new one
        try:
            if state.decant_gtin_results_win and state.decant_gtin_results_win.winfo_exists():
                state.decant_gtin_results_win.destroy()
        except Exception:
            pass

        # Display results in new window
        state.decant_gtin_results_win = tk.Toplevel(frame)
        result_win = state.decant_gtin_results_win
        result_win.title("Decant Search Results")
        result_win.configure(bg="#2b2b2b")

        table = tk.Frame(result_win, bg="#2b2b2b")
        table.pack(fill="both", expand=True, padx=10, pady=10)

        headers = ("Location", "Item", "On hand qty", "LP", "Select")
        for c, h in enumerate(headers):
            tk.Label(
                table, text=h,
                bg="#2b2b2b", fg="white",
                bd=1, relief="solid", padx=5, pady=2
            ).grid(row=0, column=c, sticky="nsew")
            table.columnconfigure(c, weight=1)

        def on_select(row):
            # Call scale selection logic
            try:
                lp = row["LOGISTICS_UNIT"]
                item_to_send = gtin if row.get("UM_MATCH", 0) else ""
                print(f"[DEBUG] on_select called - LP: {lp}, Item: '{item_to_send}', UM_MATCH: {row.get('UM_MATCH', 0)}")
                
                success, msg = select_on_scale(lp, item_to_send)
                
                if not success:
                    # Show full error in popup
                    messagebox.showerror("Selection Error", f"Failed to select on scale:\n\n{msg}")
                    
                    # Show brief message in UI
                    msg_var.set("Error - see popup")
                    msg_lbl.config(fg="red")
                    
                    # Auto-clear after 3 seconds
                    def reset_message():
                        msg_var.set("Enter a gtin and click Search")
                        msg_lbl.config(fg="white")
                    frame.after(3000, reset_message)
                else:
                    msg_var.set(msg)
                    msg_lbl.config(fg="white")
                    
            except Exception as e:
                # Handle unexpected errors
                error_details = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
                messagebox.showerror("Unexpected Error", error_details)
                
                msg_var.set("Error - see popup")
                msg_lbl.config(fg="red")
                
                def reset_message():
                    msg_var.set("Enter a gtin and click Search")
                    msg_lbl.config(fg="white")
                frame.after(3000, reset_message)
            
            if state.decant_gtin_results_win and state.decant_gtin_results_win.winfo_exists():
                state.decant_gtin_results_win.destroy()

        for r, row in enumerate(rows, start=1):
            values = (
                row.get("LOCATION", ""),
                row.get("ITEM", ""),
                row.get("ON_HAND_QTY", ""),
                row.get("LOGISTICS_UNIT", "")
            )
            for c, val in enumerate(values):
                tk.Label(
                    table, text=val,
                    bg="#2b2b2b", fg="white",
                    bd=1, relief="solid", padx=5, pady=2
                ).grid(row=r, column=c, sticky="nsew")
            ttk.Button(
                table, text="Select",
                command=lambda rw=row: on_select(rw)
            ).grid(row=r, column=len(values), sticky="nsew")

    search_btn = ttk.Button(frame, text="Search", command=on_search)
    search_btn.grid(row=2, column=1, padx=5)

    # Results placeholder
    results_frame = tk.Frame(frame, bg="#2b2b2b")
    results_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(10,0))
    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(1, weight=1)

    frame.bind_all("<Return>", lambda event: on_search())

    return frame

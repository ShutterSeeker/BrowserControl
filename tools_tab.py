import tkinter as tk
from tkinter import ttk
from browser_control.launcher import select_on_scale
import requests

IP = "10.110.2.145"
PORT = "5000"

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
    loc = department_var.get()
    if not (loc.startswith("DECANT.WS") or loc.lower().startswith("palletizingstation")):
        return
    current_result_win = {"win": None}

    tools_frame = tk.Frame(notebook, bg="#2b2b2b", padx=10, pady=10)
    notebook.add(tools_frame, text="Tools")

    for c in range(3):
        tools_frame.columnconfigure(c, weight=1)

    tools_error_var = tk.StringVar()
    tools_error_var.set("Mark totes as arrived" if loc.lower().startswith("palletizingstation") else "Pallet LP lookup by GTIN")
    error_lbl = tk.Label(
        tools_frame,
        textvariable=tools_error_var,
        bg="#2b2b2b",
        fg="white",
        font=("Segoe UI", 10),
        wraplength=200,
        justify="center"
    )
    error_lbl.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(5,15))

    entry_label_text = "Tote:" if loc.lower().startswith("palletizingstation") else "GTIN:"
    entry_var = tk.StringVar()
    input_label = tk.Label(tools_frame, text=entry_label_text, bg="#2b2b2b", fg="white", font=("Segoe UI", 10))
    input_label.grid(row=1, column=0, sticky="e")
    input_entry = ttk.Entry(tools_frame, textvariable=entry_var, font=("Segoe UI", 10))
    input_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5)

    RESULTS_ROW = 4
    results_frame = tk.Frame(tools_frame, bg="#2b2b2b")
    results_frame.grid(row=RESULTS_ROW, column=0, columnspan=3, sticky="nsew", pady=(10,0))
    tools_frame.rowconfigure(RESULTS_ROW, weight=1)

    def rebuild_tab():
        # Remove old Tools tab
        for i in range(notebook.index("end")):
            if notebook.tab(i, "text") == "Tools":
                notebook.forget(i)
                break
        # Recreate and grab updated variable
        global current_tools_error_var
        _, current_tools_error_var = create_tools_tab(notebook, department_var)


    def show_confirmation(totes, container_id):
    # Clear search input section (label, entry, button)
        for widget in [input_label, input_entry, search_btn]:
            widget.grid_remove()

        # Use the existing error_var to display the confirmation text
        tools_error_var.set(f"You are about to mark {totes} totes as arrived. Do you wish to proceed?")

        # Add confirm/cancel buttons
        btn_frame = tk.Frame(tools_frame, bg="#2b2b2b")
        btn_frame.grid(row=1, column=0, columnspan=3, pady=10)

        def on_confirm():
            try:
                resp = requests.post(f"http://{IP}:{PORT}/update_pallet_arrived_by_tote", json={"PARENT_CONTAINER_ID": container_id}, timeout=5)
                resp.raise_for_status()
                
                rebuild_tab()

                # Switch back to the Tools tab
                for i in range(notebook.index("end")):
                    if notebook.tab(i, "text") == "Tools":
                        notebook.select(i)
                        break

                current_tools_error_var.set("Marked as arrived successfully!")
            except Exception as e:
                current_tools_error_var.set(f"Error confirming: {e}")
            finally:
                btn_frame.destroy()

        def on_cancel():
            rebuild_tab()

            # Switch back to the Tools tab
            for i in range(notebook.index("end")):
                if notebook.tab(i, "text") == "Tools":
                    notebook.select(i)
                    break


        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Confirm", command=on_confirm, style="Danger.TButton").pack(side=tk.LEFT, padx=5)

    def on_search():
        for w in results_frame.winfo_children():
            w.destroy()
        val = entry_var.get().strip()
        if not val:
            tools_error_var.set("Enter value in field")
            return

        if loc.lower().startswith("palletizingstation"):
            try:
                resp = requests.post(f"http://{IP}:{PORT}/select_pallet_arrived_by_tote", json={"tote": val}, timeout=5)
                data = resp.json()

                if resp.status_code != 200:
                    msg = data.get("MSG") or data.get("message") or "Unknown error"
                    show_error_popup("Error", msg)
                    return

                msg = data.get("MSG", "")
                totes = data["TOTES_IN_TRANSIT"]
                cid = data["PARENT_CONTAINER_ID"]
                if msg:
                    tools_error_var.set(msg)
                    return

                if totes == 0:
                    tools_error_var.set(f"There are no totes to mark as arrived on pallet {cid}.")
                    return
                
                show_confirmation(totes, cid)

            except requests.exceptions.ConnectionError:
                tools_error_var.set("Backend is not running")
            except requests.exceptions.Timeout:
                tools_error_var.set("Backend request timed out")
            except Exception as e:
                show_error_popup("Exception", str(e))

        else:  # DECANT.WS logic (unchanged)
            try:
                resp = requests.post(f"http://{IP}:{PORT}/lookup_lp_by_gtin", json={"gtin": val, "department": loc}, timeout=5)
                resp.raise_for_status()
                rows = resp.json()
            except Exception as e:
                tools_error_var.set(f"Error: {e}")
                return

            if not rows:
                tools_error_var.set("No results")
                return

            result_win = tk.Toplevel(tools_frame)
            current_result_win["win"] = result_win
            result_win.title("GTIN Search Results")
            result_win.configure(bg="#2b2b2b")

            table = tk.Frame(result_win, bg="white", bd=1, relief="solid")
            table.pack(fill="both", expand=True, padx=10, pady=10)
            headers = ("Location", "Item", "On hand qty", "To location", "License plate", "Select")
            for c, h in enumerate(headers):
                tk.Label(table, text=h, font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="white", bd=1, relief="solid", padx=10, pady=2).grid(row=0, column=c, sticky="nsew")
                table.columnconfigure(c, weight=1)
            for r, row in enumerate(rows, start=1):
                values = (row.get("LOCATION", ""), row.get("ITEM", ""), row.get("ON_HAND_QTY", ""), row.get("TO_LOC", ""), row.get("LOGISTICS_UNIT", ""))
                for c, val in enumerate(values):
                    tk.Label(table, text=val, font=("Segoe UI", 10), bg="#2b2b2b", fg="white", bd=1, relief="solid", padx=10, pady=2).grid(row=r, column=c, sticky="nsew")
                ttk.Button(table, text="Select", command=lambda rw=row, win=result_win: _on_select(rw, tools_error_var, entry_var.get(), win)).grid(row=r, column=5, sticky="nsew")

    def _on_select(row, error_var, gtin, result_win):
        if row.get("UM_MATCH", 0):
            success, msg = select_on_scale(row["LOGISTICS_UNIT"], gtin)
        else:
            success, msg = select_on_scale(row["LOGISTICS_UNIT"], "")
        if not success:
            error_var.set(msg)
        if result_win and result_win.winfo_exists():
            result_win.destroy()

    btn_text = "Arrive" if loc.lower().startswith("palletizingstation") else "Search"
    search_btn = ttk.Button(tools_frame, text=btn_text, command=on_search)
    search_btn.grid(row=3, column=0, columnspan=3, pady=(10,0))

    return tools_frame, tools_error_var
# tools_slotstax.py

import tkinter as tk
from tkinter import ttk
import requests
from browser_control.constants import IP, PORT
from browser_control.utils import flash_message

def show_error_popup(title, message):
    popup = tk.Toplevel()
    popup.title(title)
    popup.configure(bg="#2b2b2b")
    popup.geometry("600x300")

    lbl = tk.Label(popup, text="Error Details:", bg="#2b2b2b", fg="white")
    lbl.pack(pady=(10, 0))

    text_box = tk.Text(popup, wrap="word", bg="white", fg="black")
    text_box.insert("1.0", message)
    text_box.config(state="normal")
    text_box.pack(fill="both", expand=True, padx=10, pady=10)

    text_box.focus()

def build_slotstax_tools(parent):
    """
    Build the "SlotStax" tools tab for marking pallets as arrived by tote.
    """
    frame = tk.Frame(parent, bg="#2b2b2b", padx=10, pady=10)

    # Status message label
    msg_var = tk.StringVar(value="Mark entire pallet as arrived by tote")
    msg_lbl = tk.Label(
        frame,
        textvariable=msg_var,
        bg="#2b2b2b",
        fg="white",
        wraplength=200
    )
    msg_lbl.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

    # Tote entry
    tote_var = tk.StringVar()
    input_label = tk.Label(frame, text="Tote:", bg="#2b2b2b", fg="white")
    input_label.grid(row=1, column=0, sticky="e", pady=5)
    tote_entry = ttk.Entry(frame, textvariable=tote_var)
    tote_entry.grid(row=1, column=1, sticky="ew", padx=(0, 5))


    # Confirmation UI inside the tab
    def show_confirmation(totes, container_id):
        # hide input UI
        input_label.grid_remove()
        tote_entry.grid_remove()
        arrive_btn.grid_remove()
        s = "s"
        if totes == 1:
            s = ""

        msg_var.set(f"You are about to mark {totes} tote{s} as arrived. Do you wish to proceed?")

        btn_frame = tk.Frame(frame, bg="#2b2b2b")
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)

        # Internal function to perform the arrival update
        def do_update_arrival(container_id):
            try:
                resp = requests.post(
                    f"http://{IP}:{PORT}/update_pallet_arrived_by_tote",
                    json={"PARENT_CONTAINER_ID": container_id},
                    timeout=5
                )
                resp.raise_for_status()
                reset_form()
                flash_message(msg_lbl, msg_var, f"{totes} tote{s} marked as arrived on pallet {container_id}", "success")
            except Exception as e: 
                show_error_popup("Error", str(e))
                flash_message(msg_lbl, msg_var, "Error confirming", "error")

        def on_confirm():
            do_update_arrival(container_id)
            

        def on_cancel():
            reset_form()
            msg_var.set("Mark entire pallet as arrived by tote")

        def reset_form():
            btn_frame.destroy()
            input_label.grid()
            tote_entry.grid()
            arrive_btn.grid()

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=on_cancel)
        cancel_btn.grid(row=0, column=0, padx=5)
        confirm_btn = ttk.Button(btn_frame, text="Confirm", style="Danger.TButton", command=on_confirm)
        confirm_btn.grid(row=0, column=1, padx=5)

    # Handler for the Arrive button
    def on_arrive_click():
        val = tote_var.get().strip()
        if not val:
            flash_message(msg_lbl, msg_var, "Please enter a tote", "error")
            return
        try:
            resp = requests.post(
                f"http://{IP}:{PORT}/select_pallet_arrived_by_tote",
                json={"tote": val},
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json()

            if resp.status_code != 200:
                msg = data.get("MSG") or data.get("message") or "Unknown error"
                show_error_popup("Error", msg)
                flash_message(msg_lbl, msg_var, "Error: See popup window", "error")
                return

            msg = data.get("MSG", "")
            totes = data.get("TOTES_IN_TRANSIT", 0)
            cid = data.get("PARENT_CONTAINER_ID")

            if msg:
                flash_message(msg_lbl, msg_var, msg, "error")
                return

            if totes == 0:
                msg = f"There are no totes to mark as arrived on pallet {cid}."
                flash_message(msg_lbl, msg_var, msg, "error")
                return

            show_confirmation(totes, cid)

        except requests.exceptions.ConnectionError:
            msg = "Backend is not running"
            flash_message(msg_lbl, msg_var, msg, "error")
        except requests.exceptions.Timeout:
            msg = "Backend request timed out"
            flash_message(msg_lbl, msg_var, msg, "error")
        except Exception as e:
            show_error_popup("Error", msg)
            flash_message(msg_lbl, msg_var, "Error: See popup window", "error")

    # Arrive button
    arrive_btn = ttk.Button(frame, text="Arrive", command=on_arrive_click)
    arrive_btn.grid(row=2, column=1, padx=5)
    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(1, weight=1)

    frame.bind_all("<Return>", lambda event: on_arrive_click())

    return frame
# tab_home.py
# Home tab with login and browser control

# Standard library imports
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
import threading
import os
import shutil
import json
import webbrowser
import subprocess
from functools import partial

# Third-party imports
import win32gui
import requests

# Local imports
import state
import config
import tab_tools
from chrome import start_threads_parallel, reorganize_windows, run_ahk_zoom
from utils import validate_credentials, flash_message, get_path
from constants import USER_FILE
from updater import get_latest_release_info, install_update_direct

def disable_all_clicks():
    if state.click_blocker is not None:
        return  # already exists

    blocker = tk.Frame(state.root, bg="", highlightthickness=0, bd=0)
    blocker.place(relx=0, rely=0, relwidth=1, relheight=1)

    for seq in ("<ButtonPress>", "<ButtonRelease>", "<Motion>"):
        blocker.bind(seq, lambda e: "break")

    state.click_blocker = blocker

def enable_all_clicks():
    if state.click_blocker:
        state.click_blocker.destroy()
        state.click_blocker = None

def close_chrome():
    """Close both Chrome windows. This function should be called in a background thread."""
    def close_dc():
        if state.driver_dc:
            try: 
                state.driver_dc.quit()
            except: 
                pass
        state.driver_dc = None
        state.dc_event.clear()
        state.dc_win = None

    def close_sc():
        if state.driver_sc:
            try: 
                state.driver_sc.quit()
            except: 
                pass
        state.driver_sc = None
        state.sc_event.clear()
        state.sc_win = None
        state.sc_hwnd = None

    # Close both in parallel for speed
    t1 = threading.Thread(target=close_dc, daemon=True)
    t2 = threading.Thread(target=close_sc, daemon=True)

    t1.start()
    t2.start()
    
    # Wait for both to finish (but this should be in a background thread already)
    t1.join(timeout=5)  # Don't wait forever
    t2.join(timeout=5)

def logout(parent, frame):
    state.username = None
    state.password = None
    state.logged_in = False  # Clear logged in state

    # Close Chrome in background (non-blocking)
    def close_async():
        close_chrome()
    
    threading.Thread(target=close_async, daemon=True).start()

     # Rebuild login screen immediately (don't wait for Chrome to close)
    parent.forget(frame)
    if state.tools_frame:
        try:
            parent.forget(state.tools_frame)
        except tk.TclError:
            pass  # Already removed
        state.tools_frame = None  # Clear the reference
    
    # Refresh settings tab to hide user-specific settings
    if state.settings_frame and hasattr(state.settings_frame, 'load_user_settings'):
        state.settings_frame.load_user_settings()
    
    new_tab = build_home_tab(parent, "Logout successful!")
    parent.insert(0, new_tab, text="Home")
    parent.select(new_tab)
    
def show_main_ui(parent, frame):

    msg_var = tk.StringVar()

    # Make 3 columns for centering
    for i in range(3):
        frame.columnconfigure(i, weight=1)

    # Top labels centered
    msg_lbl = tk.Label(frame, textvariable=msg_var, bg="#2b2b2b", fg="white")
    msg_lbl.grid(row=0, column=0, columnspan=3, pady=(10, 2), sticky="n")
    tk.Label(frame, textvariable=state.department_var, bg="#2b2b2b", fg="white").grid(row=1, column=0, columnspan=3, pady=(0, 10), sticky="n")


    def on_logout(parent, frame):
        if messagebox.askyesno("Confirm Logout", "This will close chrome. Are you sure you want to log out?"):
            msg_var.set("Logging out...")
            logout(parent, frame)

    # Buttons
    logout_btn = ttk.Button(frame, text="Logout", command=lambda: on_logout(parent, frame))
    logout_btn.grid(row=2, column=1, padx=5, pady=(10, 0))
    logout_btn.state(['disabled'])

    def on_reorganize():
        response, status = reorganize_windows()
        flash_message(msg_lbl, msg_var, response, status)

    reorganize_btn = ttk.Button(frame, text="Reorganize", command=on_reorganize)
    reorganize_btn.grid(row=2, column=2, padx=5, pady=(10, 0))
    reorganize_btn.state(['disabled'])

    def on_run_ahk_zoom(zoom):
        response, status = run_ahk_zoom(zoom)
        flash_message(msg_lbl, msg_var, response, status)

    zoom_btn_100 = ttk.Button(frame, text="100%", command=lambda: on_run_ahk_zoom("100"))
    zoom_btn_100.grid(row=3, column=1, padx=5, pady=(10, 0))
    zoom_btn_100.state(['disabled'])

    zoom_btn_custom = ttk.Button(frame, text=f"{state.zoom_var.get()}%", command=lambda: on_run_ahk_zoom(state.zoom_var.get()))
    zoom_btn_custom.grid(row=3, column=2, padx=5, pady=(10, 0))
    zoom_btn_custom.state(['disabled'])

    def update_zoom_button_text(*_):
        zoom_btn_custom.config(text=f"{state.zoom_var.get()}%")

    state.zoom_var.trace_add("write", update_zoom_button_text)


    def wait_for_both():
        """
        Wait for both DC and SC events to be set using threading.
        This is more responsive than polling - triggers immediately when both are ready.
        """
        import time
        start_wait_time = time.time()
        
        def check_ready():
            # Use threading.Event.wait() with timeout for instant response
            # Wait for DC event (20 second timeout)
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  Waiting for DC event... (at {time.time() - state.login_start_time:.2f}s)")
            
            dc_success = state.dc_event.wait(timeout=20)
            if not dc_success:
                print("[WARN] DC event timeout")
                state.root.after(0, handle_launch_failure)
                return
            
            dc_ready_time = time.time()
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  DC event RECEIVED at {dc_ready_time - state.login_start_time:.2f}s from login press")
            
            # Wait for SC event (20 second timeout)
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  DC done, now waiting for SC event... (at {time.time() - state.login_start_time:.2f}s)")
            
            sc_success = state.sc_event.wait(timeout=20)
            if not sc_success:
                print("[WARN] SC event timeout")
                state.root.after(0, handle_launch_failure)
                return
            
            sc_ready_time = time.time()
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  SC event RECEIVED at {sc_ready_time - state.login_start_time:.2f}s from login press")
            
            # Both ready! Update UI immediately
            if hasattr(state, 'login_start_time'):
                total_time = time.time() - state.login_start_time
                print(f"[PERF] ⏱️  'Ready!' displayed in {total_time:.2f}s from login button press")
            state.root.after(0, on_both_ready)
        
        def on_both_ready():
            """Called when both browsers are ready - runs on UI thread"""
            state.relaunched = False
            enable_all_clicks()

            # Show "Ready!" message FIRST (don't wait for Tools tab to build)
            flash_message(msg_lbl, msg_var, "Ready!", status='success')

            # Enable all buttons immediately
            for widget in frame.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.state(['!disabled'])
            
            # Build Tools tab in background (non-blocking)
            def build_tools_async():
                try:
                    print("[PERF] ⏱️  Building Tools tab in background...")
                    tools_tab = tab_tools.build_tools_tab()
                    # Schedule adding the tab on UI thread
                    state.root.after(0, lambda: state.notebook.add(tools_tab, text="Tools"))
                    print("[PERF] ⏱️  Tools tab added")
                except Exception as e:
                    print(f"[ERROR] Failed to build Tools tab: {e}")
            
            threading.Thread(target=build_tools_async, daemon=True).start()
        
        def handle_launch_failure():
            """Handle browser launch failure - runs on UI thread"""
            if not state.relaunched:
                state.relaunched = True
                print("[WARN] One or both windows failed to launch. Attempting relaunch.")
                state.should_abort = True
                state.root.after(100, close_chrome)  # shut down any launched windows
                enable_all_clicks()
                flash_message(msg_lbl, msg_var, "Failed. Attempting relaunch...", status='error')
                profile_path = get_path("profiles")
                if os.path.isdir(profile_path):
                    shutil.rmtree(profile_path)
                    print(f"Deleted folder: {profile_path}")
                else:
                    print(f"Nothing found at: {profile_path}")
                state.should_abort = False
                disable_all_clicks()
                start_threads_parallel()  # relaunch everything (50% faster with parallel launch!)
                wait_for_both()  # Try again
            else:
                # Second failure - give up
                state.relaunched = False
                print("[WARN] One or both windows failed to relaunch.")
                state.should_abort = True
                state.root.after(100, close_chrome)  # shut down any launched windows
                enable_all_clicks()
                profile_path = get_path("profiles")
                if os.path.isdir(profile_path):
                    shutil.rmtree(profile_path)
                    print(f"Deleted folder: {profile_path}")
                else:
                    print(f"Nothing found at: {profile_path}")
                state.should_abort = False
                tools_tab = tab_tools.build_tools_tab()
                state.notebook.add(tools_tab, text="Tools")

                flash_message(msg_lbl, msg_var, "Failed to launch", status='error')

                for widget in frame.winfo_children(): # Enable all buttons
                    if isinstance(widget, ttk.Button):
                        widget.state(['!disabled'])
        
        # Run the check in a background thread so it doesn't block the UI
        threading.Thread(target=check_ready, daemon=True).start()

    msg_var.set("Launching Chrome...")
    wait_for_both()

    return frame

def build_home_tab(parent, msg):

    user_path = get_path(USER_FILE)

    def load_usernames():
        if os.path.exists(user_path):
            try:
                with open(user_path, "r") as f:
                    data = json.load(f)
                    
                # Handle backwards compatibility
                if data and isinstance(data[0], str):
                    # Old format: ["username1", "username2"]
                    # Convert to new format with current timestamp, removing duplicates
                    import time
                    current_time = time.time()
                    seen_usernames = set()
                    converted_data = []
                    
                    for username in data:
                        username_lower = username.lower()
                        if username_lower not in seen_usernames:
                            seen_usernames.add(username_lower)
                            converted_data.append({"username": username_lower, "last_login": current_time})
                    
                    # Sort by most recent login (newest first)
                    converted_data.sort(key=lambda x: x["last_login"], reverse=True)
                    
                    # Save converted format immediately
                    with open(user_path, "w") as f:
                        json.dump(converted_data, f, indent=2)
                    
                    return converted_data
                
                # Always sort the loaded data by most recent login
                data.sort(key=lambda x: x["last_login"], reverse=True)
                return data
            except:
                return []
        return []

    def save_usernames(usernames):
        with open(user_path, "w") as f:
            json.dump(usernames, f, indent=2)

    def remember_username(username):
        import time
        usernames = load_usernames()
        username_lower = username.lower()
        current_time = time.time()
        
        # Find existing user (case-insensitive)
        existing_index = None
        for i, user_data in enumerate(usernames):
            if user_data["username"].lower() == username_lower:
                existing_index = i
                break
        
        if existing_index is not None:
            # Update existing user's timestamp
            usernames[existing_index]["last_login"] = current_time
        else:
            # Add new user
            usernames.append({"username": username_lower, "last_login": current_time})
        
        # Sort by most recent login (newest first)
        usernames.sort(key=lambda x: x["last_login"], reverse=True)
        save_usernames(usernames)

    def remove_username(username):
        usernames = load_usernames()
        # Find and remove user (case-insensitive)
        usernames = [user_data for user_data in usernames if user_data["username"].lower() != username.lower()]
        save_usernames(usernames)

    class AutoSuggestEntry(tk.Entry):
        def __init__(self, master, **kwargs):
            super().__init__(master, **kwargs)
            usernames_data = load_usernames()
            # Extract just the usernames for suggestions (sorted by most recent)
            self.suggestions = [user_data["username"] for user_data in usernames_data]
            self.popup = None
            self.mousewheel_binding = None
            self.deleting = False  # Flag to prevent closing on delete
            self.selected_index = -1  # Track selected suggestion
            self.filtered_matches = []  # Current filtered matches
            self.dragging = False  # True while mouse button held inside popup (prevents premature close)
            self.drag_sensitivity = 0.35  # Lower = slower drag scroll
            self.bind("<KeyRelease>", self.on_key_release)
            self.bind("<KeyPress>", self.on_key_press)
            self.bind("<FocusIn>", self.on_focus_in)
            self.bind("<FocusOut>", self.on_focus_out)

        def on_focus_in(self, event=None):
            """Show suggestions only if not already visible to avoid rebuild flicker."""
            if self.popup and self.popup.winfo_exists():
                return
            self.show_suggestions()
        
        def is_pointer_inside_popup(self):
            """Return True if current pointer is inside the suggestions popup."""
            if not self.popup:
                return False
            try:
                x = self.popup.winfo_rootx()
                y = self.popup.winfo_rooty()
                w = self.popup.winfo_width()
                h = self.popup.winfo_height()
                px = self.winfo_pointerx()
                py = self.winfo_pointery()
                return x <= px <= x + w and y <= py <= y + h
            except tk.TclError:
                return False

        def on_key_press(self, event=None):
            """Handle special key presses for navigation"""
            if not self.popup or not self.filtered_matches:
                return
            
            if event.keysym == 'Down':
                if self.selected_index == -1:
                    # First time pressing down - select first item
                    self.selected_index = 0
                elif self.selected_index == len(self.filtered_matches) - 1:
                    # At bottom - wrap to top
                    self.selected_index = 0
                else:
                    # Move down
                    self.selected_index += 1
                self.update_selection_highlight()
                self.scroll_to_selected()
                return "break"  # Prevent default behavior
            elif event.keysym == 'Up':
                if self.selected_index == -1:
                    # First time pressing up - select last item
                    self.selected_index = len(self.filtered_matches) - 1
                elif self.selected_index == 0:
                    # At top - wrap to bottom
                    self.selected_index = len(self.filtered_matches) - 1
                else:
                    # Move up
                    self.selected_index -= 1
                self.update_selection_highlight()
                self.scroll_to_selected()
                return "break"  # Prevent default behavior
            elif event.keysym in ('Return', 'Tab'):
                if self.selected_index >= 0 and self.selected_index < len(self.filtered_matches):
                    selected_user = self.filtered_matches[self.selected_index]
                    self.select_user(selected_user)
                    return "break"  # Prevent default behavior
            elif event.keysym == 'Escape':
                self.hide_popup()
                return "break"

        def on_key_release(self, event=None):
            # Skip processing for navigation keys
            if event and event.keysym in ('Down', 'Up', 'Return', 'Tab', 'Escape'):
                return
            
            # Convert to lowercase as user types
            current_pos = self.index(tk.INSERT)
            current_text = self.get()
            lowercase_text = current_text.lower()
            
            if current_text != lowercase_text:
                self.delete(0, tk.END)
                self.insert(0, lowercase_text)
                self.icursor(current_pos)
            
            # Reset selection when typing
            self.selected_index = -1
            self.show_suggestions(event)
        
        def on_focus_out(self, event=None):
            # If pointer still inside popup or dragging, don't close yet
            if self.deleting:
                return
            if self.dragging:
                return
            if self.is_pointer_inside_popup():
                # Re-check again shortly; user may start a drag
                self.master.after(200, lambda: (not self.dragging) and (not self.deleting) and (not self.is_pointer_inside_popup()) and self.hide_popup())
                return
            # Normal behavior: schedule close
            self.master.after(120, self.hide_popup)

        def show_suggestions(self, event=None):
            # Preserve scroll position if reopening
            last_scroll = None
            if self.popup and getattr(self, 'canvas', None):
                try:
                    last_scroll = self.canvas.yview()[0]
                except Exception:
                    last_scroll = None
            # Destroy existing popup (only if not actively dragging)
            if self.popup and not self.dragging:
                self.popup.destroy()

            # Filter usernames case-insensitively
            val = self.get().lower()
            matches = [u.lower() for u in self.suggestions if val in u.lower()]
            # Exclude exact match (avoid showing the same item as the field value)
            matches = [u for u in matches if u != val]
            self.filtered_matches = matches  # Store for navigation
            if not matches:
                self.selected_index = -1
                return

            # --- Geometry calculations ---
            row_height = 33
            max_visible_rows = 10
            visible_rows = min(len(matches), max_visible_rows)
            popup_height = row_height * visible_rows

            font = tkfont.Font(font=self.cget("font"))
            longest_text = max(matches, key=lambda s: len(s)) if matches else ""
            text_width_px = font.measure(longest_text)
            # Reserve space for scrollbar (always) and delete column
            scrollbar_width = 16
            delete_col_width = 38  # includes padding
            popup_width = text_width_px + delete_col_width + scrollbar_width + 40  # base padding

            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = self.winfo_rootx() + 30
            y_below = self.winfo_rooty() + self.winfo_height() + 2
            y_above = self.winfo_rooty() - popup_height - 2

            space_below = screen_height - y_below
            if y_below + popup_height > screen_height:
                space_above = self.winfo_rooty() - 2
                if y_above >= 0 and space_above >= space_below:
                    y = max(0, y_above)
                else:
                    y = y_below
                    available_height = space_below - 10
                    popup_height = min(popup_height, available_height)
            else:
                y = y_below

            if x + popup_width > screen_width:
                x = screen_width - popup_width - 10

            # --- Build popup ---
            self.popup = tk.Toplevel(self)
            self.popup.attributes("-topmost", True)
            self.popup.overrideredirect(True)
            self.popup.configure(bg="#2b2b2b", bd=1, relief="solid")
            self.popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

            # Determine if scrollbar is needed
            needs_scrollbar = len(matches) > max_visible_rows
            
            # Store canvas reference for scrolling
            self.canvas = None
            
            # Root container - different layout based on scrollbar need
            if needs_scrollbar:
                container = tk.Frame(self.popup, bg="#2b2b2b")
                container.pack(fill="both", expand=True)
                container.grid_rowconfigure(0, weight=1)  # Make row expandable
                container.grid_columnconfigure(0, weight=1)  # canvas column expandable
                container.grid_columnconfigure(1, weight=0, minsize=scrollbar_width)  # scrollbar column fixed
                # no focus juggling; rely on pointer-based close logic

                # Canvas + internal frame
                canvas = tk.Canvas(container, bg="#2b2b2b", highlightthickness=0)
                canvas.grid(row=0, column=0, sticky="nsew")
                inner = tk.Frame(canvas, bg="#2b2b2b")
                canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")
                
                # Store canvas reference for scrolling
                self.canvas = canvas
                # Restore previous scroll position if available and valid
                if last_scroll is not None:
                    self.popup.after(30, lambda: canvas.yview_moveto(last_scroll))

                # Scrollbar for when needed
                style = ttk.Style()
                try:
                    style.theme_use("clam")
                except tk.TclError:
                    pass
                style.configure("Suggest.Vertical.TScrollbar", background="#4c4c4c", troughcolor="#1a1a1a", bordercolor="#1a1a1a", arrowcolor="#6c6c6c")
                style.map("Suggest.Vertical.TScrollbar", background=[("active", "#6c6c6c"), ("pressed", "#7c7c7c")])
                scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Suggest.Vertical.TScrollbar")
                scrollbar.grid(row=0, column=1, sticky="nsew")
                canvas.configure(yscrollcommand=scrollbar.set)

                # Configure canvas window to fill available width
                def configure_canvas_window(event=None):
                    canvas_width = canvas.winfo_width()
                    if canvas_width > 1:
                        canvas.itemconfig(canvas_window, width=canvas_width)
                
                canvas.bind("<Configure>", configure_canvas_window)
                
                container_frame = inner
            else:
                # No scrollbar needed - direct container
                container_frame = self.popup

            # Mousewheel and vertical-only drag support (only when scrollbar is present)
            if needs_scrollbar:
                def on_mousewheel(event):
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                self.winfo_toplevel().bind_all("<MouseWheel>", on_mousewheel)
                self.mousewheel_binding = on_mousewheel

                canvas.is_dragging = False
                self.dragging = False
                canvas.drag_start_y = 0
                canvas.drag_origin_top = 0.0

                def clamp_view():
                    top, bottom = canvas.yview()
                    if top < 0:
                        canvas.yview_moveto(0)
                    elif bottom > 1:
                        height_fraction = bottom - top
                        new_top = max(0, 1 - height_fraction)
                        canvas.yview_moveto(new_top)

                def on_drag_start(event):
                    canvas.is_dragging = True
                    self.dragging = True
                    canvas.drag_start_y = event.y_root
                    canvas.drag_origin_top = canvas.yview()[0]
                    canvas.config(cursor="hand2")

                def on_drag_motion(event):
                    if not canvas.is_dragging:
                        return
                    dy = event.y_root - canvas.drag_start_y
                    bbox = canvas.bbox("all")
                    if not bbox:
                        return
                    _, _, _, content_bottom = bbox
                    content_height = content_bottom
                    visible_height = canvas.winfo_height()
                    if content_height <= visible_height:
                        return
                    fraction_per_pixel = 1.0 / (content_height - visible_height)
                    # Apply sensitivity to slow down drag scrolling
                    new_top = canvas.drag_origin_top - dy * fraction_per_pixel * self.drag_sensitivity
                    new_top = max(0.0, min(1.0, new_top))
                    canvas.yview_moveto(new_top)
                    clamp_view()

                def on_drag_end(event):
                    canvas.is_dragging = False
                    self.dragging = False
                    clamp_view()
                    canvas.config(cursor="")

                canvas.bind("<ButtonPress-1>", on_drag_start)
                canvas.bind("<B1-Motion>", on_drag_motion)
                canvas.bind("<ButtonRelease-1>", on_drag_end)

            # Configure container frame to expand properly
            container_frame.grid_columnconfigure(0, weight=1) if hasattr(container_frame, 'grid_columnconfigure') else None
            if hasattr(container_frame, 'grid_columnconfigure'):
                container_frame.grid_columnconfigure(1, minsize=delete_col_width, weight=0)

            # Store row widgets for selection highlighting
            self.row_widgets = []
            
            # Track drag threshold for distinguishing clicks from drags
            self.drag_threshold = 5  # pixels - movement less than this is considered a click
            
            # Populate rows (grid for consistent layout)
            for i, user in enumerate(matches):
                row = tk.Frame(container_frame, bg="#2b2b2b", height=row_height)
                if needs_scrollbar:
                    row.grid(row=i, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
                else:
                    row.pack(fill="x")
                
                row.grid_columnconfigure(0, weight=1)
                row.grid_columnconfigure(1, minsize=delete_col_width, weight=0)
                row.grid_propagate(False)  # Keep fixed height

                lbl = tk.Label(row, text=user, font=30, pady=5, padx=10, anchor="w", bg="#2b2b2b", fg="white")
                lbl.grid(row=0, column=0, sticky="ew")

                del_frame = tk.Frame(row, bg="#2b2b2b", width=delete_col_width - 8, height=row_height - 6)
                del_frame.grid(row=0, column=1, padx=(4, 4), pady=3, sticky="e")
                del_frame.grid_propagate(False)
                del_lbl = tk.Label(del_frame, text="✕", fg="red", bg="#2b2b2b", cursor="hand2", font=("Segoe UI", 10, "bold"))
                del_lbl.place(relx=0.5, rely=0.5, anchor="center")
                del_lbl.bind("<Button-1>", partial(self.delete_user, user))
                
                # Store widgets for selection highlighting
                self.row_widgets.append((row, lbl, del_frame, del_lbl))

                def make_hover_handlers(row_widget, lbl_widget, frame_widget, del_widget, row_index):
                    def on_enter_row(event):
                        # Don't override keyboard selection highlighting
                        if self.selected_index != row_index:
                            color = "#7B7B7B"
                            for widget in (row_widget, lbl_widget, frame_widget, del_widget):
                                widget.configure(bg=color)
                    
                    def on_leave_row(event):
                        # Restore keyboard selection or normal color
                        if self.selected_index == row_index:
                            color = "#5c5c5c"  # Keep keyboard selection color
                        else:
                            color = "#2b2b2b"  # Normal color
                        for widget in (row_widget, lbl_widget, frame_widget, del_widget):
                            widget.configure(bg=color)
                    
                    def on_enter_x_only(event):
                        # Only highlight X button if not keyboard selected
                        if self.selected_index != row_index:
                            frame_widget.configure(bg="#7B7B7B")
                            del_widget.configure(bg="#7B7B7B")
                    
                    def on_leave_x_only(event):
                        # Reset X button based on selection state
                        if self.selected_index == row_index:
                            color = "#5c5c5c"  # Keep keyboard selection color
                        else:
                            color = "#2b2b2b"  # Normal color
                        frame_widget.configure(bg=color)
                        del_widget.configure(bg=color)
                    
                    return on_enter_row, on_leave_row, on_enter_x_only, on_leave_x_only

                on_enter_row, on_leave_row, on_enter_x_only, on_leave_x_only = make_hover_handlers(row, lbl, del_frame, del_lbl, i)
                
                # Enable drag scrolling on row widgets when scrollbar is present
                if needs_scrollbar:
                    # Click vs vertical drag differentiation
                    drag_state = {'start_y': None, 'moved': False}

                    def row_press(event, username=user):
                        drag_state['start_y'] = event.y_root
                        drag_state['moved'] = False
                        on_drag_start(event)

                    def row_motion(event):
                        if drag_state['start_y'] is not None and abs(event.y_root - drag_state['start_y']) > self.drag_threshold:
                            drag_state['moved'] = True
                        on_drag_motion(event)

                    def row_release(event, username=user):
                        on_drag_end(event)
                        if drag_state['start_y'] is not None and not drag_state['moved']:
                            self.select_user(username)
                        drag_state['start_y'] = None
                        drag_state['moved'] = False

                    for widget in (row, lbl):
                        widget.bind("<ButtonPress-1>", row_press)
                        widget.bind("<B1-Motion>", row_motion)
                        widget.bind("<ButtonRelease-1>", row_release)
                else:
                    # No scrollbar - just bind click event directly
                    lbl.bind("<Button-1>", partial(self.select_user, user))
                
                # Row and label hover - highlight everything
                row.bind("<Enter>", on_enter_row)
                row.bind("<Leave>", on_leave_row)
                lbl.bind("<Enter>", on_enter_row)
                lbl.bind("<Leave>", on_leave_row)
                
                # X button hover - only highlight X
                del_frame.bind("<Enter>", on_enter_x_only)
                del_frame.bind("<Leave>", on_leave_x_only)
                del_lbl.bind("<Enter>", on_enter_x_only)
                del_lbl.bind("<Leave>", on_leave_x_only)

            # Keep scrollregion in sync with content size; preserve current view to avoid jumps
            if needs_scrollbar:
                def _update_region(event=None):
                    if hasattr(canvas, 'is_dragging') and canvas.is_dragging:
                        return
                    try:
                        current_top = canvas.yview()[0]
                    except Exception:
                        current_top = 0.0
                    bbox = canvas.bbox("all")
                    if bbox:
                        canvas.configure(scrollregion=bbox)
                    # prevent any horizontal drift
                    canvas.xview_moveto(0)
                    # restore vertical position
                    canvas.yview_moveto(current_top)
                inner.bind("<Configure>", _update_region)
                self.popup.after(30, _update_region)


        def update_selection_highlight(self):
            """Update visual highlighting for keyboard selection"""
            if not hasattr(self, 'row_widgets') or not self.row_widgets:
                return
            
            # Clear all highlights first
            for i, (row, lbl, del_frame, del_lbl) in enumerate(self.row_widgets):
                if i == self.selected_index:
                    # Highlight selected row
                    color = "#5c5c5c"  # Different color for keyboard selection
                    for widget in (row, lbl, del_frame, del_lbl):
                        widget.configure(bg=color)
                else:
                    # Reset to normal
                    color = "#2b2b2b"
                    for widget in (row, lbl, del_frame, del_lbl):
                        widget.configure(bg=color)

        def scroll_to_selected(self):
            """Scroll the canvas to ensure selected item is visible"""
            if not self.canvas or self.selected_index < 0 or not hasattr(self, 'row_widgets'):
                return
            
            if self.selected_index >= len(self.row_widgets):
                return
            
            # Get the selected row widget
            selected_row = self.row_widgets[self.selected_index][0]
            
            # Get canvas dimensions
            canvas_height = self.canvas.winfo_height()
            if canvas_height <= 1:
                return
            
            # Get row position and height
            row_height = 33  # Same as defined earlier
            row_top = self.selected_index * row_height
            row_bottom = row_top + row_height
            
            # Get current scroll region
            scroll_region = self.canvas.cget("scrollregion").split()
            if len(scroll_region) < 4:
                return
            
            total_height = float(scroll_region[3])
            if total_height <= canvas_height:
                return  # No scrolling needed
            
            # Get current view
            view_top, view_bottom = self.canvas.yview()
            visible_top = view_top * total_height
            visible_bottom = view_bottom * total_height
            
            # Check if selected row is visible
            if row_top < visible_top:
                # Row is above visible area - scroll up
                new_top = max(0, row_top - 10)  # 10px padding
                self.canvas.yview_moveto(new_top / total_height)
            elif row_bottom > visible_bottom:
                # Row is below visible area - scroll down
                new_bottom = min(total_height, row_bottom + 10)  # 10px padding
                new_top = max(0, new_bottom - canvas_height)
                self.canvas.yview_moveto(new_top / total_height)

        def hide_popup(self):
            if self.popup:
                # Clean up mousewheel binding if it exists
                if self.mousewheel_binding:
                    try:
                        self.winfo_toplevel().unbind_all("<MouseWheel>")
                    except tk.TclError:
                        # Widget may have been destroyed already
                        pass
                    self.mousewheel_binding = None
                
                self.popup.destroy()
                self.popup = None
                self.selected_index = -1
                self.filtered_matches = []

        def select_user(self, username, event=None):
            self.delete(0, tk.END)
            self.insert(0, username)
            self.hide_popup()
            # Move focus to password field
            password_entry.focus_set()

        def delete_user(self, username, event=None):
            # Set flag to prevent popup from closing
            self.deleting = True
            
            # Find the original username in suggestions (might have different case)
            original_username = None
            for u in self.suggestions:
                if u.lower() == username.lower():
                    original_username = u
                    break
            
            if original_username:
                remove_username(original_username)
                # Reload suggestions (now sorted by most recent)
                usernames_data = load_usernames()
                self.suggestions = [user_data["username"] for user_data in usernames_data]
                # Refresh the popup without closing it
                self.show_suggestions()
            
            # Reset flag after a short delay
            self.master.after(200, lambda: setattr(self, 'deleting', False))


    frame = tk.Frame(parent, bg="#2b2b2b", padx=20, pady=20)
    # Feedback label
    msg_var = tk.StringVar(value=msg)
    msg_lbl = tk.Label(frame, textvariable=msg_var, fg="white", bg="#2b2b2b")
    msg_lbl.grid(row=0, column=0, columnspan=2, pady=(0, 15))
    flash_message(msg_lbl, msg_var, msg, "success")

    # Username + Password
    tk.Label(frame, text="Username:", bg="#2b2b2b", fg="white").grid(row=1, column=0, sticky="e", pady=5)
    tk.Label(frame, text="Password:", bg="#2b2b2b", fg="white").grid(row=2, column=0, sticky="e", pady=5)
    # Keep inputs narrower and aligned (no full-width stretch)
    try:
        frame.grid_columnconfigure(1, weight=0)
    except Exception:
        pass

    # Wrap username entry in a frame to add a clear (✕) button
    username_wrapper = tk.Frame(frame, bg="#2b2b2b")
    username_wrapper.grid(row=1, column=1, pady=5, sticky="w")
    username_wrapper.grid_columnconfigure(0, weight=1)
    username_wrapper.grid_columnconfigure(1, weight=0)

    username_entry = AutoSuggestEntry(username_wrapper, width=16)
    username_entry.grid(row=0, column=0, sticky="w")

    def clear_username():
        username_entry.delete(0, tk.END)
        # Refresh suggestions (will show all since empty)
        username_entry.show_suggestions()
        username_entry.focus_set()

    # Style a small clear button to look like an inline control
    try:
        style = ttk.Style()
        style.configure("ClearButton.TButton", padding=(4, 0))
    except Exception:
        pass

    clear_btn = ttk.Button(username_wrapper, text="✕", style="ClearButton.TButton", cursor="hand2", width=2)
    clear_btn.grid(row=0, column=1, padx=(6,0))
    clear_btn.configure(command=clear_username)

    # Always visible; no hiding logic. Ensure suggestions update on typing.
    username_entry.bind("<KeyRelease>", lambda e: username_entry.on_key_release(e))
    password_entry = ttk.Entry(frame, show="*", width=16)
    password_entry.grid(row=2, column=1, pady=5, sticky="w")

    def on_login_submit():
        username = username_entry.get()
        password = password_entry.get()
        print(username)

        if validate_credentials(username, password):
            remember_username(username)
            state.username = username
            state.password = password
            state.logged_in = True  # Set logged in state
            
            # Fetch user settings BEFORE launching browsers
            user_theme = "dark"  # Default to dark mode
            user_zoom = "200"    # Default zoom
            
            # OPTIMIZATION: Check cache first (pre-loaded during splash screen)
            if username in state.user_settings_cache:
                cached_settings = state.user_settings_cache[username]
                user_theme = cached_settings.get("theme", "dark")
                user_zoom = cached_settings.get("zoom", "200")
                print(f"[LOGIN] ✓ Loaded user settings from CACHE: theme={user_theme}, zoom={user_zoom}")
            else:
                # Cache miss - user may have been added after app launch
                # Fallback to API call
                print(f"[LOGIN] User '{username}' not in cache, fetching from API...")
                try:
                    from constants import IP, PORT
                    resp = requests.post(
                        f"http://{IP}:{PORT}/get_user_settings",
                        json={"username": username},
                        timeout=5
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    # Update with user settings from database
                    user_zoom = data.get("zoom", "200")
                    user_theme = data.get("theme", "dark")
                    
                    # Store in cache for next time
                    state.user_settings_cache[username] = {
                        "theme": user_theme,
                        "zoom": user_zoom
                    }
                    
                    print(f"[LOGIN] ✓ Loaded user settings from API: theme={user_theme}, zoom={user_zoom}")
                except Exception as e:
                    print(f"[WARNING] Failed to load user settings from API, using defaults (dark mode): {e}")
            
            # ALWAYS set these in config, even if all lookups fail (use defaults)
            state.zoom_var.set(user_zoom)
            config.cfg["zoom_var"] = user_zoom
            config.cfg["theme"] = user_theme
            print(f"[LOGIN] Applied theme to config.cfg: theme={config.cfg['theme']}, zoom={config.cfg['zoom_var']}")
            print(f"[LOGIN] DEBUG: config.cfg type: {type(config.cfg)}")
            print(f"[LOGIN] DEBUG: config.cfg.get('theme'): {config.cfg.get('theme', 'NOT_FOUND')}")
            print(f"[LOGIN] DEBUG: config.cfg id: {id(config.cfg)}")
            print(f"[LOGIN] DEBUG: config.cfg contents: {dict(config.cfg)}")
            
            # Start performance timer
            import time
            state.login_start_time = time.time()
            print(f"[PERF] ⏱️  Starting browser launch timer at login button press")
            
            hide_login_form()
            show_main_ui(parent, frame)
            start_threads_parallel()  # Use optimized parallel launch (50% faster!)
            state.root.after(100, disable_all_clicks)
            
            # Refresh settings tab to show user-specific settings
            if state.settings_frame and hasattr(state.settings_frame, 'load_user_settings'):
                state.root.after(200, state.settings_frame.load_user_settings)
        else:
            flash_message(msg_lbl, msg_var, "Invalid username or password", "error")
            password_entry.focus_set()

    # Buttons
    button_container = tk.Frame(frame, bg="#2b2b2b")
    button_container.grid(row=3, column=0, columnspan=2, pady=(15, 0))
    button_container.columnconfigure(0, weight=1)
    button_container.columnconfigure(1, weight=1)

    submit_btn = ttk.Button(button_container, text="Login", command=on_login_submit)

    if state.update_available:
        def auto_update():
            """Download and install update automatically (with fallback)"""
            # Disable buttons during update
            update_btn.config(state="disabled", text="Downloading...")
            submit_btn.config(state="disabled")
            
            def download_and_install():
                try:
                    # Get release info
                    release_info = get_latest_release_info()
                    if not release_info:
                        state.root.after(0, lambda: messagebox.showerror("Update Failed", "Could not fetch update information."))
                        state.root.after(0, lambda: update_btn.config(state="normal", text="Update"))
                        state.root.after(0, lambda: submit_btn.config(state="normal"))
                        return
                    
                    # Direct exe replacement via PowerShell
                    if release_info.get('exe_url'):
                        state.root.after(0, lambda: update_btn.config(text="Downloading..."))
                        
                        if install_update_direct(release_info['exe_url']):
                            # Exit silently to allow PowerShell script to proceed
                            def exit_app():
                                # Force exit immediately without dialog
                                import sys
                                sys.exit(0)
                            
                            state.root.after(0, exit_app)
                            return
                    
                    # Update failed
                    state.root.after(0, lambda: messagebox.showerror(
                        "Update Failed",
                        "Could not install update.\n\n"
                        "Please download manually from:\n"
                        "https://github.com/ShutterSeeker/BrowserControl/releases"
                    ))
                    state.root.after(0, lambda: update_btn.config(state="normal", text="Update"))
                    state.root.after(0, lambda: submit_btn.config(state="normal"))
                
                except Exception as e:
                    state.root.after(0, lambda: messagebox.showerror("Update Failed", f"An error occurred: {str(e)}"))
                    state.root.after(0, lambda: update_btn.config(state="normal", text="Update"))
                    state.root.after(0, lambda: submit_btn.config(state="normal"))
            
            # Run download in background thread
            threading.Thread(target=download_and_install, daemon=True).start()

        update_btn = ttk.Button(button_container, text="Update", command=auto_update, style="Update.TButton")
        update_btn.grid(row=0, column=0, padx=(0, 5))

        submit_btn.grid(row=0, column=1, padx=(5, 0))
    else:
        submit_btn.grid(row=0, column=0, columnspan=2)
    
    # Show connection warning if update check failed
    if hasattr(state, 'update_message') and ("Connection failed" in state.update_message or "Update check failed" in state.update_message):
        warning_label = tk.Label(
            frame,
            text=f"⚠️ {state.update_message}",
            font=("Segoe UI", 9),
            bg="#2b2b2b",
            fg="#ffaa00",
            wraplength=400,
            justify="center"
        )
        warning_label.grid(row=4, column=0, columnspan=2, pady=(10, 0))


    def hide_login_form():
        # Destroy username suggestion artifacts (popup + wrapper)
        try:
            if hasattr(username_entry, 'popup') and username_entry.popup:
                username_entry.popup.destroy()
        except Exception:
            pass
        try:
            username_wrapper.destroy()
        except Exception:
            pass
        try:
            password_entry.destroy()
        except Exception:
            pass
        msg_lbl.grid_remove()
        submit_btn.grid_remove()

        # Remove Update button and its container if present so it doesn't linger under other UI
        try:
            button_container.destroy()
        except Exception:
            pass

        for widget in frame.grid_slaves():
            if isinstance(widget, tk.Label) and widget.cget("text") in ("Username:", "Password:"):
                widget.grid_remove()

    def is_osk_in_foreground():
        hwnd = win32gui.GetForegroundWindow()
        return "on-screen keyboard" in win32gui.GetWindowText(hwnd).lower()

    def get_osk_hwnd():
        osk_hwnd = None
        def callback(hwnd, _):
            nonlocal osk_hwnd
            if "on-screen keyboard" in win32gui.GetWindowText(hwnd).lower():
                osk_hwnd = hwnd
        win32gui.EnumWindows(callback, None)
        return osk_hwnd
    
    def wait_until_osk_has_focus():
        if not is_osk_in_foreground():
            print("[DEBUG] Waiting for focus")
            frame.after(100, wait_until_osk_has_focus)
        else:
            frame.after(200, lambda: username_entry.focus_force())
            frame.after(800, lambda: username_entry.focus_force())

    def revive_osk(hwnd):
        if win32gui.IsIconic(hwnd):
            print("OSK is minimized, launching again to revive.")
            subprocess.Popen("osk.exe", shell=True)
            frame.after(100, wait_until_osk_has_focus)
        else:
            print("OSK is already visible, focusing username.")
            frame.after(100, lambda: username_entry.focus_force())

    def revive_and_refocus():
        hwnd = get_osk_hwnd()
        if hwnd:
            revive_osk(hwnd)
        else:
            frame.after(100, lambda: username_entry.focus_force())

    frame.after(200, revive_and_refocus)
    frame.bind_all("<Return>", lambda event: on_login_submit())
    return frame
# browser_control/zoom_controls.py

class ZoomControls:
    """
    Encapsulates both the UI buttons and the zoom logic for Scale RF pages.
    """
    def __init__(self, driver_sc, zoom_var):
        self.driver = driver_sc
        self.zoom_var = zoom_var

    def is_palletizing(self, department):
        return department.startswith("PalletizingStation")

    def toggle_zoom(self) -> str:
        # return "" on success, or an error message
        if not self.zoom_var.get().isdigit():
            return "Zoom is set to Off"
        try:
            # compute target zoom as a float (e.g., '150' -> 1.5)
            target_zoom = int(self.zoom_var.get()) / 100.0
            for handle in self.driver.window_handles:
                self.driver.switch_to.window(handle)
                url = self.driver.current_url
                if not url.startswith("https://scale20.byjasco.com/RF"):
                    continue

                current = self.driver.execute_script(
                    "return document.body.style.zoom || '1'"
                )
                current_val = float(current)
                new_zoom = 1.0 if current_val == target_zoom else target_zoom
                #print(f"Target: {target_zoom}. Current: {current_val}. New: {new_zoom}")
                self.driver.execute_script(
                    "document.body.style.zoom = arguments[0]", new_zoom
                )
            return f"Zoom set to {int(self.zoom_var.get())}%"
        except Exception:
            return "No Scale window found"
from pynput import mouse
import logging

class ClickTracker:
    def __init__(self, click_callback):
        """
        Accepts a callback click_callback(x, y, button, pressed).
        """
        self.click_callback = click_callback
        self.listener = None

    def _on_click(self, x, y, button, pressed):
        try:
            self.click_callback(x, y, button, pressed)
        except Exception as e:
            logging.error(f"Error in ClickTracker callback: {e}")

    def start(self):
        if self.listener is None:
            self.listener = mouse.Listener(on_click=self._on_click)
            self.listener.start()
            logging.info("ClickTracker started.")

    def stop(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener.join()
            self.listener = None
            logging.info("ClickTracker stopped.")

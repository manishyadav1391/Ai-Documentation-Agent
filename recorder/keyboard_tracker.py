from pynput import keyboard
import logging
from .uia_helper import get_focused_element_info

class KeyboardTracker:
    def __init__(self, input_callback):
        """
        input_callback is called with (field_name, value, is_sensitive) when text input is flushed.
        """
        self.input_callback = input_callback
        self.listener = None
        self.buffer = []
        self.field_info = None
        self.is_sensitive = False

    def start(self):
        self.buffer = []
        self.field_info = None
        self.is_sensitive = False
        if self.listener is None:
            self.listener = keyboard.Listener(on_press=self._on_press)
            self.listener.start()
            logging.info("KeyboardTracker started.")

    def stop(self):
        self.flush()
        if self.listener is not None:
            self.listener.stop()
            self.listener.join()
            self.listener = None
            logging.info("KeyboardTracker stopped.")

    def flush(self):
        if not self.buffer:
            return None
        
        typed_text = "".join(self.buffer).strip()
        self.buffer = []
        
        if not typed_text:
            self.field_info = None
            self.is_sensitive = False
            return None
        
        field_name = "Unknown Field"
        is_pw = self.is_sensitive
        if self.field_info:
            field_name = self.field_info.get("name") or self.field_info.get("class_name") or "Input Field"
            if self.field_info.get("is_password"):
                is_pw = True
        
        # Redact value if password or sensitive
        value = "[REDACTED]" if is_pw else typed_text
        
        # Call callback
        try:
            self.input_callback(field_name, value, is_pw)
        except Exception as e:
            logging.error(f"Error in KeyboardTracker callback: {e}")
            
        self.field_info = None
        self.is_sensitive = False

    def _on_press(self, key):
        try:
            # Check boundary keys that should trigger a flush
            if key in (keyboard.Key.enter, keyboard.Key.tab, keyboard.Key.esc):
                self.flush()
                return

            # Check if it's a character
            if hasattr(key, 'char') and key.char is not None:
                # If buffer is empty, capture focused element info
                if not self.buffer:
                    self._capture_focus()
                
                if not self.is_sensitive:
                    self.buffer.append(key.char)
                else:
                    self.buffer.append("*")  # placeholder just to keep buffer non-empty
            
            elif key == keyboard.Key.space:
                if not self.buffer:
                    self._capture_focus()
                if not self.is_sensitive:
                    self.buffer.append(" ")
                else:
                    self.buffer.append("*")
                    
            elif key == keyboard.Key.backspace:
                if self.buffer:
                    self.buffer.pop()
                    
        except Exception as e:
            logging.error(f"Error in KeyboardTracker _on_press: {e}")

    def _capture_focus(self):
        try:
            info = get_focused_element_info()
            if info:
                self.field_info = info
                # Check password or sensitive keywords
                is_pw = info.get("is_password", False)
                name_lower = (info.get("name") or "").lower()
                class_lower = (info.get("class_name") or "").lower()
                sensitive_keywords = ["password", "passwort", "passwd", "pin", "cvv", "creditcard", "otp", "one-time"]
                
                if is_pw or any(kw in name_lower or kw in class_lower for kw in sensitive_keywords):
                    self.is_sensitive = True
                else:
                    self.is_sensitive = False
            else:
                self.field_info = None
                self.is_sensitive = False
        except Exception as e:
            logging.error(f"Error capturing focus: {e}")
            self.field_info = None
            self.is_sensitive = False

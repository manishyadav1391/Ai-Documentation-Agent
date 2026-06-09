import os
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from .uia_helper import get_uia_instance, shutdown_uia, get_element_at
from .window_tracker import get_active_window_info
from .click_tracker import ClickTracker
from .keyboard_tracker import KeyboardTracker
from .screenshot import capture_screenshot
from .exporter import Exporter

@dataclass
class ActionStep:
    step_no: int
    timestamp: str
    action_type: str
    window_title: str
    screenshot: str
    metadata: dict

class Recorder:
    def __init__(self, base_dir=".", step_signal=None):
        """
        base_dir: Root directory where sessions/ and output/ will live.
        step_signal: Optional PyQt signal to emit step updates to the UI.
        """
        self.base_dir = os.path.abspath(base_dir)
        self.exporter = Exporter(self.base_dir)
        self.step_signal = step_signal
        
        self.click_tracker = ClickTracker(self._on_click)
        self.keyboard_tracker = KeyboardTracker(self._on_input)
        
        self.is_recording = False
        self.session_id = None
        self.session_path = None
        self.screenshots_path = None
        
        self.steps = []
        self.step_counter = 0
        
        self.start_time = None
        self.end_time = None
        
        self.last_hwnd = None
        self.primary_app_name = "Generic Desktop Application"

    def start(self):
        if self.is_recording:
            return
            
        logging.info("Starting recorder session...")
        self.is_recording = True
        self.steps = []
        self.step_counter = 0
        self.start_time = datetime.now()
        self.last_hwnd = None
        
        # 1. Initialize UI Automation
        get_uia_instance()
        
        # 2. Create session directories
        timestamp_str = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.session_id = f"recording_{timestamp_str}"
        self.session_path, self.screenshots_path = self.exporter.create_session_layout(self.session_id)
        
        # 3. Start listener threads
        self.click_tracker.start()
        self.keyboard_tracker.start()
        
        # 4. Log initial window state
        self._check_window_change()
        
        logging.info(f"Recording started. Session ID: {self.session_id}")

    def stop(self):
        if not self.is_recording:
            return None
            
        logging.info("Stopping recorder session...")
        self.is_recording = False
        self.end_time = datetime.now()
        
        # 1. Stop trackers
        self.click_tracker.stop()
        self.keyboard_tracker.stop() # This flushes any pending typing
        
        # 2. Shutdown UI Automation COM interface
        shutdown_uia()
        
        # 3. Convert steps to dictionary format and save
        steps_dict = [asdict(step) for step in self.steps]
        
        # Set primary app name based on the most common window title or first window title
        app_name = self.primary_app_name
        if self.steps:
            app_name = self.steps[0].window_title
            
        self.exporter.save_session(
            session_id=self.session_id,
            steps=steps_dict,
            start_time=self.start_time,
            end_time=self.end_time,
            app_name=app_name
        )
        
        # 4. Packaging
        zip_path = self.exporter.export_zip(self.session_id)
        
        logging.info("Recorder session stopped and zipped.")
        return zip_path

    def _on_click(self, x, y, button, pressed):
        if not self.is_recording:
            return
            
        if pressed:
            logging.info(f"Click detected at ({x}, {y}) with button {button}")
            
            # 1. Flush any typed text first before capturing click
            self.keyboard_tracker.flush()
            
            # 2. Track window change
            self._check_window_change()
            
            # 3. Get UI Element properties at clicked coordinates
            element_info = None
            highlight_rect = None
            element_name = "UI Element"
            try:
                element_info = get_element_at(x, y)
                if element_info:
                    highlight_rect = element_info.get("rect")
                    element_name = element_info.get("name") or element_info.get("class_name") or "UI Element"
            except Exception as e:
                logging.error(f"Error checking element at point: {e}")
                
            # 4. Capture screenshot
            self.step_counter += 1
            filename = f"{self.step_counter:03d}_click.png"
            filepath = os.path.join(self.screenshots_path, filename)
            
            capture_screenshot(filepath, click_coords=(x, y), highlight_rect=highlight_rect)
            
            # 5. Log action step
            win_info = get_active_window_info()
            metadata = {
                "x": x,
                "y": y,
                "button": str(button),
                "element_name": element_name,
                "url": win_info.get("url", "")
            }
            
            step = ActionStep(
                step_no=self.step_counter,
                timestamp=datetime.now().isoformat(),
                action_type="click",
                window_title=win_info.get("title", "Unknown"),
                screenshot=os.path.join("screenshots", filename),
                metadata=metadata
            )
            
            self.steps.append(step)
            self._emit_step_signal()

    def _on_input(self, field_name, value, is_sensitive):
        if not self.is_recording:
            return
            
        logging.info(f"Input detected on field '{field_name}'")
        
        # 1. Check window change
        self._check_window_change()
        
        # 2. Capture screenshot
        self.step_counter += 1
        filename = f"{self.step_counter:03d}_input.png"
        filepath = os.path.join(self.screenshots_path, filename)
        
        # Try to highlight the text field if we have its bounding rect
        highlight_rect = None
        if self.keyboard_tracker.field_info:
            highlight_rect = self.keyboard_tracker.field_info.get("rect")
            
        capture_screenshot(filepath, highlight_rect=highlight_rect)
        
        # 3. Log action step
        win_info = get_active_window_info()
        metadata = {
            "field_name": field_name,
            "value": value,
            "url": win_info.get("url", "")
        }
        
        step = ActionStep(
            step_no=self.step_counter,
            timestamp=datetime.now().isoformat(),
            action_type="input",
            window_title=win_info.get("title", "Unknown"),
            screenshot=os.path.join("screenshots", filename),
            metadata=metadata
        )
        
        self.steps.append(step)
        self._emit_step_signal()

    def _check_window_change(self):
        """
        Checks if foreground window has changed and logs it as a separate step.
        """
        win_info = get_active_window_info()
        hwnd = win_info.get("hwnd")
        
        if hwnd and hwnd != self.last_hwnd:
            if self.last_hwnd is not None:
                # Log a window change event
                self.step_counter += 1
                filename = f"{self.step_counter:03d}_window_change.png"
                filepath = os.path.join(self.screenshots_path, filename)
                
                # Take screenshot of the new active window (no element highlighted)
                capture_screenshot(filepath)
                
                metadata = {
                    "class_name": win_info.get("class_name", ""),
                    "url": win_info.get("url", "")
                }
                
                step = ActionStep(
                    step_no=self.step_counter,
                    timestamp=datetime.now().isoformat(),
                    action_type="window_change",
                    window_title=win_info.get("title", "Unknown"),
                    screenshot=os.path.join("screenshots", filename),
                    metadata=metadata
                )
                
                self.steps.append(step)
                self._emit_step_signal()
                logging.info(f"Window changed: {win_info.get('title')}")
                
            self.last_hwnd = hwnd
            self.primary_app_name = win_info.get("title")

    def _emit_step_signal(self):
        if self.step_signal:
            try:
                # Emit step count and the latest step description
                latest_step = self.steps[-1]
                desc = f"{latest_step.action_type.capitalize()}"
                if latest_step.action_type == "click":
                    desc += f" on {latest_step.metadata.get('element_name')}"
                elif latest_step.action_type == "input":
                    desc += f" in {latest_step.metadata.get('field_name')}"
                elif latest_step.action_type == "window_change":
                    desc += f" to {latest_step.window_title}"
                self.step_signal.emit(self.step_counter, desc)
            except Exception as e:
                logging.error(f"Failed to emit step signal: {e}")

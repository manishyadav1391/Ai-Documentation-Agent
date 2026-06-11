import os
import logging
import re
import queue
import threading
import time as time_mod
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pynput import mouse as pynput_mouse
from .uia_helper import get_uia_instance, shutdown_uia, get_element_at, CONTROL_TYPE_NAMES
from .window_tracker import get_active_window_info
from .click_tracker import ClickTracker
from .keyboard_tracker import KeyboardTracker
from .screenshot import capture_screenshot
from .exporter import Exporter

# Issue #1: Windows to ignore (the recorder's own UI)
IGNORED_WINDOWS = [
    "Documentation Bot - Recorder",
    "Documentation Bot",
]

# Issue #2: Taskbar / system tray class names to ignore
IGNORED_CLASS_NAMES = {
    "Shell_TrayWnd",
    "TrayNotifyWnd",
    "TaskListThumbnailWnd",
    "NotifyIconOverflowWindow",
    "MSTaskSwWClass",
    "MSTaskListWClass",
}

# Issue #2: Control types to ignore (ScrollBar=50014, Thumb=50027, TitleBar=50037)
IGNORED_CONTROL_TYPES = {50014, 50027, 50037}

def sanitize_filename(name):
    if not name:
        return "element"
    # Replace non-alphanumeric characters with underscores, collapse consecutive underscores, strip
    name_clean = re.sub(r'[^a-zA-Z0-9]+', '_', name).strip('_').lower()
    return name_clean[:30] # Limit to 30 chars for readability

@dataclass
class ActionStep:
    step_no: int
    timestamp: str
    action_type: str
    window_title: str
    screenshot: str
    metadata: dict
    business_action: str = ""

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
        
        # Issue #11: Duplicate click detection
        self.last_click_info = {"key": None, "time": 0}
        
        # Thread-safe event queue and background processor
        self.queue = queue.Queue()
        self.worker_thread = None

    def start(self):
        if self.is_recording:
            return
            
        logging.info("Starting recorder session...")
        self.is_recording = True
        self.steps = []
        self.step_counter = 0
        self.start_time = datetime.now()
        self.last_hwnd = None
        self.last_click_info = {"key": None, "time": 0}
        
        # 1. Initialize UI Automation
        get_uia_instance()
        
        # 2. Create session directories
        timestamp_str = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.session_id = f"recording_{timestamp_str}"
        self.session_path, self.screenshots_path = self.exporter.create_session_layout(self.session_id)
        
        # 3. Start queue worker thread
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        
        # 4. Queue initial window state check
        self.queue.put(("init_window", (datetime.now(),)))
        
        # 5. Start listener threads
        self.click_tracker.start()
        self.keyboard_tracker.start()
        
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
        
        # 2. Signal worker thread to terminate and wait
        self.queue.put((None, None))
        if self.worker_thread:
            self.worker_thread.join(timeout=3.0)
            self.worker_thread = None
            
        # 3. Shutdown UI Automation COM interface
        shutdown_uia()
        
        # 3. Convert steps to dictionary format and save
        steps_dict = [asdict(step) for step in self.steps]
        
        # Issue #15: Set primary app name based on the most common window title
        app_name = self.primary_app_name
        if self.steps:
            titles = [s.window_title for s in self.steps
                      if s.window_title not in IGNORED_WINDOWS and s.window_title != "Unknown"]
            if titles:
                app_name = Counter(titles).most_common(1)[0][0]
            else:
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
        
        # Issue #9: Only record left clicks
        if pressed and button == pynput_mouse.Button.left:
            logging.info(f"Click detected at ({x}, {y}) with button {button}")
            # Flush typed text synchronously so that it is queued before this click event
            self.keyboard_tracker.flush()
            self.queue.put(("click", (x, y, button, datetime.now())))

    def _on_input(self, field_name, value, is_sensitive):
        if not self.is_recording:
            return
            
        logging.info(f"Input detected on field '{field_name}'")
        self.queue.put(("input", (field_name, value, is_sensitive, datetime.now())))

    def _process_queue(self):
        while self.is_recording:
            try:
                # Wait for next event with a timeout
                event = self.queue.get(timeout=0.5)
                if event[0] is None:
                    # Sentinel received, exit thread loop
                    self.queue.task_done()
                    break
            except queue.Empty:
                continue
                
            try:
                event_type, data = event
                if event_type == "init_window":
                    self._check_window_change()
                elif event_type == "click":
                    x, y, button, ts = data
                    self._handle_click(x, y, button, ts)
                elif event_type == "input":
                    field_name, value, is_sensitive, ts = data
                    self._handle_input(field_name, value, is_sensitive, ts)
            except Exception as e:
                logging.error(f"Error handling event in worker thread: {e}")
            finally:
                self.queue.task_done()

    def _should_skip_click(self, element_info, highlight_rect, win_info):
        """
        Issue #2 & #10: Determines whether a click should be ignored.
        Returns True only for definitive noise (taskbar, scrollbar, recorder window).
        Does NOT skip clicks just because UIA can't resolve the element —
        the screenshot will use click_coords circle as fallback highlight.
        """
        # Issue #1: Skip clicks in the recorder's own window
        title = win_info.get("title", "")
        if title in IGNORED_WINDOWS:
            return True
        
        if element_info:
            cls_name = element_info.get("class_name", "")
            control_type = element_info.get("control_type", 0)
            
            # Skip clicks on taskbar / system tray elements
            if cls_name in IGNORED_CLASS_NAMES:
                return True
            
            # Skip clicks on scrollbars, thumbs, title bars
            if control_type in IGNORED_CONTROL_TYPES:
                return True
        
        return False

    def _handle_click(self, x, y, button, ts):
        # 1. Check window change (internal tracking only, Issue #3)
        self._check_window_change()
        
        # 2. Get UI Element properties at clicked coordinates
        element_info = None
        highlight_rect = None
        element_name = "UI Element"
        logging.info("=" * 80)
        logging.info(f"CLICK AT: ({x}, {y})")
        logging.info(f"ELEMENT INFO: {element_info}")
        logging.info("=" * 80)
        try:
            element_info = get_element_at(x, y)
            if element_info:
                highlight_rect = element_info.get("rect")
                logging.info(f"HIGHLIGHT RECT: {highlight_rect}")
                # Issue #7: Improved fallback chain for element name
                element_name = (
                    element_info.get("name")
                    or element_info.get("automation_id")
                    or element_info.get("class_name")
                    or CONTROL_TYPE_NAMES.get(element_info.get("control_type"), "")
                    or "UI Element"
                )
        except Exception as e:
            logging.error(f"Error checking element at point: {e}")
        
        # 3. Get window info for skip checks and metadata
        win_info = get_active_window_info()
        
        # Issue #2 & #10: Skip meaningless clicks
        if self._should_skip_click(element_info, highlight_rect, win_info):
            logging.debug(f"Skipped noise click at ({x}, {y}) — element: {element_name}")
            return
        
        # Issue #11: Duplicate click detection (same element + window within 1 second)
        now = time_mod.time()
        click_key = (element_name, win_info.get("hwnd"))
        if (self.last_click_info.get("key") == click_key and
            now - self.last_click_info.get("time", 0) < 1.0):
            logging.debug(f"Skipped duplicate click on '{element_name}'")
            return
        self.last_click_info = {"key": click_key, "time": now}
            
        # Create business action text and sanitize element name for filename
        business_action = f"Click {element_name}"
        clean_element_name = sanitize_filename(element_name)
        
        # 4. Capture screenshot
        self.step_counter += 1
        filename = f"{self.step_counter:03d}_click_{clean_element_name}.png"
        filepath = os.path.join(self.screenshots_path, filename)

        logging.info(f"FINAL RECT SENT TO SCREENSHOT = {highlight_rect}")
        capture_screenshot(
            filepath, 
            click_coords=(x, y), 
            highlight_rect=highlight_rect,
            step_no=self.step_counter,
            action_label=business_action
        )
        
        # 5. Log action step
        metadata = {
            "x": x,
            "y": y,
            "button": str(button),
            "element_name": element_name,
            "control_type_name": element_info.get("control_type_name", "") if element_info else "",
            "window_type": win_info.get("window_type", ""),
            "url": win_info.get("url", "")
        }
        
        step = ActionStep(
            step_no=self.step_counter,
            timestamp=ts.isoformat(),
            action_type="click",
            window_title=win_info.get("title", "Unknown"),
            screenshot=os.path.join("screenshots", filename),
            metadata=metadata,
            business_action=business_action
        )
        
        self.steps.append(step)
        self._emit_step_signal()

    def _handle_input(self, field_name, value, is_sensitive, ts):
        # 1. Check window change (internal tracking only, Issue #3)
        self._check_window_change()
        
        # Issue #1: Skip inputs in the recorder's own window
        win_info = get_active_window_info()
        if win_info.get("title", "") in IGNORED_WINDOWS:
            return
        
        # Create business action text and sanitize field name for filename
        masked_val = "********" if is_sensitive else value
        business_action = f"Enter '{masked_val}' in {field_name}" if field_name else f"Enter '{masked_val}'"
        clean_field_name = sanitize_filename(field_name) if field_name else "field"
        
        # 2. Capture screenshot
        self.step_counter += 1
        filename = f"{self.step_counter:03d}_input_{clean_field_name}.png"
        filepath = os.path.join(self.screenshots_path, filename)
        
        # Try to highlight the text field if we have its bounding rect
        highlight_rect = None
        if self.keyboard_tracker.field_info:
            highlight_rect = self.keyboard_tracker.field_info.get("rect")
            
        capture_screenshot(
            filepath, 
            highlight_rect=highlight_rect,
            step_no=self.step_counter,
            action_label=business_action
        )
        
        # 3. Log action step
        metadata = {
            "field_name": field_name,
            "value": value,
            "window_type": win_info.get("window_type", ""),
            "url": win_info.get("url", "")
        }
        
        step = ActionStep(
            step_no=self.step_counter,
            timestamp=ts.isoformat(),
            action_type="input",
            window_title=win_info.get("title", "Unknown"),
            screenshot=os.path.join("screenshots", filename),
            metadata=metadata,
            business_action=business_action
        )
        
        self.steps.append(step)
        self._emit_step_signal()

    def _check_window_change(self):
        """
        Issue #3: Checks if foreground window has changed.
        Tracks state internally but does NOT create exported steps.
        """
        win_info = get_active_window_info()
        hwnd = win_info.get("hwnd")
        
        if hwnd and hwnd != self.last_hwnd:
            title = win_info.get("title", "Unknown")
            
            if self.last_hwnd is not None:
                logging.info(f"Window changed: {title}")
            
            self.last_hwnd = hwnd
            # Only update primary app name if it's not an ignored window
            if title not in IGNORED_WINDOWS:
                self.primary_app_name = title

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
                self.step_signal.emit(self.step_counter, desc)
            except Exception as e:
                logging.error(f"Failed to emit step signal: {e}")

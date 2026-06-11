import win32gui
import win32process
import win32api
import os
import logging
from .uia_helper import get_browser_url

# Issue #14: Window classification sets
BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "arc.exe", "vivaldi.exe"}
OFFICE_PROCESSES = {"excel.exe", "winword.exe", "powerpnt.exe", "outlook.exe", "onenote.exe", "teams.exe"}

def classify_window(proc_name, class_name):
    """Issue #14: Classify the window type based on process name and class."""
    if proc_name in BROWSER_PROCESSES:
        return "browser"
    if proc_name in OFFICE_PROCESSES:
        return "office"
    if proc_name == "explorer.exe":
        return "file_explorer"
    if class_name in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "mintty"):
        return "terminal"
    return "desktop_app"

def get_active_window_info():
    """
    Retrieves information about the current foreground window.
    Returns a dictionary:
      - title: Window title
      - hwnd: Window handle
      - class_name: Windows window class name
      - process_name: The executable name (e.g. 'chrome.exe')
      - window_type: Classification ('browser', 'office', 'file_explorer', 'terminal', 'desktop_app')
      - url: Browser URL (if active window is Chrome, Edge, Firefox, etc.)
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {
                "title": "Desktop / Screen Lock",
                "hwnd": 0,
                "class_name": "",
                "process_name": "",
                "window_type": "desktop_app",
                "url": ""
            }
            
        title = win32gui.GetWindowText(hwnd)
        if not title:
            title = "Untitled Window"
            
        class_name = win32gui.GetClassName(hwnd)
        
        # Get process name to avoid scanning non-browser Electron apps (like VS Code, Slack, Teams)
        proc_name = ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(0x1000, False, pid) # PROCESS_QUERY_LIMITED_INFORMATION
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
            proc_name = os.path.basename(exe_path).lower()
        except Exception as proc_err:
            logging.debug(f"Could not get process name for hwnd {hwnd}: {proc_err}")
        
        # Issue #14: Classify window type
        window_type = classify_window(proc_name, class_name)
        
        url = ""
        # Check if the class name is a browser class and the process is a known browser
        if class_name in ("Chrome_WidgetWin_1", "MozillaWindowClass") and proc_name in BROWSER_PROCESSES:
            try:
                url = get_browser_url(hwnd)
            except Exception as uia_err:
                logging.debug(f"Could not retrieve browser URL: {uia_err}")
                
        return {
            "title": title,
            "hwnd": hwnd,
            "class_name": class_name,
            "process_name": proc_name,
            "window_type": window_type,
            "url": url
        }
    except Exception as e:
        logging.error(f"Error in get_active_window_info: {e}")
        return {
            "title": "Unknown",
            "hwnd": 0,
            "class_name": "",
            "process_name": "",
            "window_type": "desktop_app",
            "url": ""
        }

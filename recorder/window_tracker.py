import win32gui
import logging
from .uia_helper import get_browser_url

def get_active_window_info():
    """
    Retrieves information about the current foreground window.
    Returns a dictionary:
      - title: Window title
      - hwnd: Window handle
      - class_name: Windows window class name
      - url: Browser URL (if active window is Chrome, Edge, Firefox, etc.)
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {
                "title": "Desktop / Screen Lock",
                "hwnd": 0,
                "class_name": "",
                "url": ""
            }
            
        title = win32gui.GetWindowText(hwnd)
        if not title:
            title = "Untitled Window"
            
        class_name = win32gui.GetClassName(hwnd)
        
        url = ""
        # Check if the class name is a browser class
        # Chrome, Edge, Opera, Brave, Arc use Chrome_WidgetWin_1
        # Firefox uses MozillaWindowClass
        if class_name in ("Chrome_WidgetWin_1", "MozillaWindowClass"):
            try:
                url = get_browser_url(hwnd)
            except Exception as uia_err:
                logging.debug(f"Could not retrieve browser URL: {uia_err}")
                
        return {
            "title": title,
            "hwnd": hwnd,
            "class_name": class_name,
            "url": url
        }
    except Exception as e:
        logging.error(f"Error in get_active_window_info: {e}")
        return {
            "title": "Unknown",
            "hwnd": 0,
            "class_name": "",
            "url": ""
        }

import uiautomation as auto
import logging
import re

# Human-readable UIA Control Type names (Issue #13)
CONTROL_TYPE_NAMES = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50027: "Thumb",
    50028: "DataGrid",
    50029: "DataItem",
    50030: "Document",
    50031: "SplitButton",
    50032: "Window",
    50033: "Pane",
    50034: "Header",
    50035: "HeaderItem",
    50036: "Table",
    50037: "TitleBar",
    50038: "Separator",
}

# Dummy functions for backward compatibility with orchestrator
def get_uia_instance():
    return None

def shutdown_uia():
    pass

def _parse_rect(rect_val):
    if not rect_val:
        return None
    try:
        left = int(rect_val.left)
        top = int(rect_val.top)
        right = int(rect_val.right)
        bottom = int(rect_val.bottom)
        width = right - left
        height = bottom - top
        if width > 3 and height > 3 and width < 5000 and height < 5000:
            return {
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": width,
                "height": height
            }
    except Exception as e:
        logging.debug(f"Error parsing bounding rect: {e}")
    return None

def get_element_at(x, y):
    """
    Returns UIA element details at screen coordinates (x, y).
    """
    try:
        with auto.UIAutomationInitializerInThread():
            control = auto.ControlFromPoint(x, y)
            if control:
                name = control.Name or ""
                ctype = control.ControlType
                cls_name = control.ClassName or ""
                automation_id = control.AutomationId or ""
                rect = _parse_rect(control.BoundingRectangle)
                
                is_pw = False
                if hasattr(control, 'IsPassword'):
                    is_pw = bool(control.IsPassword)
                    
                return {
                    "name": name,
                    "control_type": ctype,
                    "control_type_name": CONTROL_TYPE_NAMES.get(ctype, control.ControlTypeName or f"Control_{ctype}"),
                    "automation_id": automation_id,
                    "class_name": cls_name,
                    "rect": rect,
                    "is_password": is_pw
                }
    except Exception as e:
        logging.error(f"Error in get_element_at: {e}")
    return None

def get_focused_element_info():
    """
    Retrieves information about the currently focused UI element.
    """
    try:
        with auto.UIAutomationInitializerInThread():
            control = auto.GetFocusedControl()
            if control:
                name = control.Name or ""
                ctype = control.ControlType
                cls_name = control.ClassName or ""
                automation_id = control.AutomationId or ""
                rect = _parse_rect(control.BoundingRectangle)
                
                is_pw = False
                if hasattr(control, 'IsPassword'):
                    is_pw = bool(control.IsPassword)
                    
                return {
                    "name": name,
                    "control_type": ctype,
                    "control_type_name": CONTROL_TYPE_NAMES.get(ctype, control.ControlTypeName or f"Control_{ctype}"),
                    "automation_id": automation_id,
                    "class_name": cls_name,
                    "rect": rect,
                    "is_password": is_pw
                }
    except Exception as e:
        logging.error(f"Error in get_focused_element_info: {e}")
    return None

def get_browser_url(hwnd):
    """
    Traverses the UIA tree of the browser window (Chrome, Edge, Firefox, etc.)
    to locate the Omnibox/address bar and retrieve the current URL.
    """
    try:
        with auto.UIAutomationInitializerInThread():
            browser = auto.ControlFromHandle(hwnd)
            if not browser:
                return ""
                
            # Try finding the Omnibox EditControl by its standard class name
            edit = browser.EditControl(ClassName="OmniboxViewViews")
            if not edit.Exists(0.05, 0.05):
                # Fallback: find any generic edit control in the browser window
                edit = browser.EditControl()
                
            if edit.Exists(0.05, 0.05):
                try:
                    url = edit.GetValuePattern().Value
                    if url:
                        if not (url.startswith("http://") or url.startswith("https://")):
                            url = "https://" + url
                        return url
                except Exception as pat_err:
                    logging.debug(f"ValuePattern failed on browser edit control: {pat_err}")
                    
            # Recursive DFS traversal fallback if simple queries fail
            def search_element(curr, depth=0):
                if depth > 12:
                    return ""
                if not curr:
                    return ""
                try:
                    ctype = curr.ControlType
                    name = curr.Name or ""
                    cls_name = curr.ClassName or ""
                    
                    # Check edit controls
                    if ctype == 50004:  # Edit
                        try:
                            val = curr.GetValuePattern().Value
                            if val:
                                is_url_like = (
                                    val.startswith("http://") or 
                                    val.startswith("https://") or 
                                    "www." in val or 
                                    (re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$", val) is not None)
                                )
                                if is_url_like:
                                    return val
                                if cls_name == "OmniboxViewViews" or "address" in name.lower() or "search" in name.lower():
                                    if "." in val and " " not in val:
                                        return val
                        except:
                            pass
                    
                    for child in curr.GetChildren():
                        res = search_element(child, depth + 1)
                        if res:
                            return res
                except Exception as e:
                    pass
                return ""
                
            return search_element(browser)
    except Exception as e:
        logging.error(f"Error in get_browser_url: {e}")
    return ""

def is_sensitive_element(x, y):
    """
    Checks if the element at screen coordinates (x, y) is sensitive (e.g., password field).
    """
    info = get_element_at(x, y)
    if info:
        if info.get("is_password"):
            return True
        name_lower = info.get("name", "").lower()
        class_lower = info.get("class_name", "").lower()
        sensitive_keywords = ["password", "passwort", "passwd", "pin", "cvv", "creditcard", "otp", "one-time password"]
        for kw in sensitive_keywords:
            if kw in name_lower or kw in class_lower:
                return True
    return False

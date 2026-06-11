import ctypes
from ctypes import wintypes
import uuid
import re
import logging

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

# GUID definition
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_uint8 * 8)
    ]
    def __init__(self, guid_str):
        u = uuid.UUID(guid_str.strip('{}'))
        self.Data1 = u.fields[0]
        self.Data2 = u.fields[1]
        self.Data3 = u.fields[2]
        self.Data4[:] = list(u.bytes[8:])

CLSID_CUIAutomation = GUID("{ff48dba4-60ef-4201-aa87-54103eef594e}")
IID_IUIAutomation = GUID("{30cbe57d-d9d0-452a-ab13-7ac5ac4825ee}")

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

HRESULT = ctypes.c_long

# Helper to call COM methods by vtable index
def call_com(interface_ptr, index, prototype, *args):
    if not interface_ptr:
        return -1
    # Convert raw python integers to ctypes pointer instances
    if isinstance(interface_ptr, int):
        interface_ptr = ctypes.c_void_p(interface_ptr)
        
    try:
        vtbl_ptr = ctypes.cast(interface_ptr, ctypes.POINTER(ctypes.c_void_p))[0]
        method_ptr = ctypes.cast(vtbl_ptr, ctypes.POINTER(ctypes.c_void_p))[index]
        func = prototype(method_ptr)
        return func(interface_ptr, *args)
    except Exception as e:
        import logging
        logging.debug(f"Error in call_com for index {index}: {e}")
        return -1

# Dummy functions for backward compatibility with orchestrator
def get_uia_instance():
    return None

def shutdown_uia():
    pass

# Element Property Accessors (takes ctypes.c_void_p or int)
def get_element_name(element_ptr):
    proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p))
    name_ptr = ctypes.c_wchar_p()
    hr = call_com(element_ptr, 23, proto, ctypes.byref(name_ptr))
    if hr == 0 and name_ptr.value:
        val = name_ptr.value
        ctypes.windll.oleaut32.SysFreeString(ctypes.cast(name_ptr, ctypes.c_void_p))
        return val
    return ""

def get_element_control_type(element_ptr):
    proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))
    ctype = ctypes.c_int()
    hr = call_com(element_ptr, 21, proto, ctypes.byref(ctype))
    if hr == 0:
        return ctype.value
    return 0

def get_element_class_name(element_ptr):
    proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p))
    name_ptr = ctypes.c_wchar_p()
    hr = call_com(element_ptr, 30, proto, ctypes.byref(name_ptr))
    if hr == 0 and name_ptr.value:
        val = name_ptr.value
        ctypes.windll.oleaut32.SysFreeString(ctypes.cast(name_ptr, ctypes.c_void_p))
        return val
    return ""

def get_element_value(element_ptr):
    proto_pat = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
    pat_ptr = ctypes.c_void_p()
    # ValuePattern = 10002
    hr = call_com(element_ptr, 16, proto_pat, 10002, ctypes.byref(pat_ptr))
    if hr == 0 and pat_ptr.value:
        proto_val = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p))
        val_ptr = ctypes.c_wchar_p()
        hr_val = call_com(pat_ptr.value, 3, proto_val, ctypes.byref(val_ptr))
        # Release pattern pointer
        call_com(pat_ptr.value, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
        if hr_val == 0 and val_ptr.value:
            val = val_ptr.value
            ctypes.windll.oleaut32.SysFreeString(ctypes.cast(val_ptr, ctypes.c_void_p))
            return val
    return ""

def is_element_password(element_ptr):
    proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL))
    is_pw = wintypes.BOOL()
    # get_CurrentIsPassword is offset 35
    hr = call_com(element_ptr, 35, proto, ctypes.byref(is_pw))
    if hr == 0:
        return bool(is_pw.value)
    return False

def get_element_rect(element_ptr):

    class UIA_RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_double),
            ("top", ctypes.c_double),
            ("right", ctypes.c_double),
            ("bottom", ctypes.c_double)
        ]

    rect = UIA_RECT()

    proto = ctypes.WINFUNCTYPE(
        HRESULT,
        ctypes.c_void_p,
        ctypes.POINTER(UIA_RECT)
    )

    hr = call_com(
        element_ptr,
        37,
        proto,
        ctypes.byref(rect)
    )

    if hr == 0:

        left = int(rect.left)
        top = int(rect.top)
        right = int(rect.right)
        bottom = int(rect.bottom)

        width = right - left
        height = bottom - top

        logging.info(
            f"UIA RECT => "
            f"L={left}, T={top}, "
            f"R={right}, B={bottom}"
        )

        if (
            width > 3 and
            height > 3 and
            width < 5000 and
            height < 5000
        ):
            return {
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": width,
                "height": height
            }

    return None

def get_element_automation_id(element_ptr):
    """Issue #7: Retrieve AutomationId for better element identification."""
    proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p))
    name_ptr = ctypes.c_wchar_p()
    # get_CurrentAutomationId: standard UIA offset 19, code offset = 19 + 10 = 29
    hr = call_com(element_ptr, 29, proto, ctypes.byref(name_ptr))
    if hr == 0 and name_ptr.value:
        val = name_ptr.value
        ctypes.windll.oleaut32.SysFreeString(ctypes.cast(name_ptr, ctypes.c_void_p))
        return val
    return ""

# API Functions (Self-contained COM Apartments)
def get_element_at(x, y):
    ctypes.windll.ole32.CoInitialize(None)
    uia_ptr = ctypes.c_void_p()
    try:
        hr = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(CLSID_CUIAutomation),
            None,
            1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(IID_IUIAutomation),
            ctypes.byref(uia_ptr)
        )
        if hr != 0 or not uia_ptr.value:
            return None
        
        proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, POINT, ctypes.POINTER(ctypes.c_void_p))
        elem_ptr = ctypes.c_void_p()
        pt = POINT(x, y)
        hr_elem = call_com(uia_ptr, 7, proto, pt, ctypes.byref(elem_ptr))
        logging.info(
            f"ElementFromPoint HR={hr_elem} "
            f"PTR={elem_ptr.value}"
        )
        if hr_elem == 0 and elem_ptr.value:
            name = get_element_name(elem_ptr)
            ctype = get_element_control_type(elem_ptr)
            cls_name = get_element_class_name(elem_ptr)
            automation_id = get_element_automation_id(elem_ptr)
            rect = get_element_rect(elem_ptr)
            is_pw = is_element_password(elem_ptr)
            
            # Release element pointer
            call_com(elem_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
            
            return {
                "name": name,
                "control_type": ctype,
                "control_type_name": CONTROL_TYPE_NAMES.get(ctype, f"Control_{ctype}"),
                "automation_id": automation_id,
                "class_name": cls_name,
                "rect": rect,
                "is_password": is_pw
            }
    except Exception as e:
      
        logging.error(f"Error in get_element_at: {e}")
    finally:
        if uia_ptr.value:
            call_com(uia_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
        ctypes.windll.ole32.CoUninitialize()
    return None

def get_focused_element_info():
    ctypes.windll.ole32.CoInitialize(None)
    uia_ptr = ctypes.c_void_p()
    try:
        hr = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(CLSID_CUIAutomation),
            None,
            1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(IID_IUIAutomation),
            ctypes.byref(uia_ptr)
        )
        if hr != 0 or not uia_ptr.value:
            return None
        
        proto = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        elem_ptr = ctypes.c_void_p()
        # GetFocusedElement is offset 9
        hr_elem = call_com(uia_ptr, 9, proto, ctypes.byref(elem_ptr))
        logging.info(f"ElementFromPoint HR = {hr_elem}")
        logging.info(f"Element Pointer = {elem_ptr.value}")
        if hr_elem == 0 and elem_ptr.value:
            name = get_element_name(elem_ptr)
            logging.info(f"ELEMENT NAME = {name}")
            ctype = get_element_control_type(elem_ptr)
            cls_name = get_element_class_name(elem_ptr)
            automation_id = get_element_automation_id(elem_ptr)
            rect = get_element_rect(elem_ptr)
            logging.info(f"ELEMENT RECT = {rect}")
            is_pw = is_element_password(elem_ptr)
            
            # Release element pointer
            call_com(elem_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
            
            return {
                "name": name,
                "control_type": ctype,
                "control_type_name": CONTROL_TYPE_NAMES.get(ctype, f"Control_{ctype}"),
                "automation_id": automation_id,
                "class_name": cls_name,
                "rect": rect,
                "is_password": is_pw
            }
    except Exception as e:
        import logging
        logging.error(f"Error in get_focused_element_info: {e}")
    finally:
        if uia_ptr.value:
            call_com(uia_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
        ctypes.windll.ole32.CoUninitialize()
    return None

def get_browser_url(hwnd):
    ctypes.windll.ole32.CoInitialize(None)
    uia_ptr = ctypes.c_void_p()
    try:
        hr = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(CLSID_CUIAutomation),
            None,
            1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(IID_IUIAutomation),
            ctypes.byref(uia_ptr)
        )
        if hr != 0 or not uia_ptr.value:
            return ""
        
        # Get element from HWND (offset 6)
        proto_handle = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        elem_ptr = ctypes.c_void_p()
        hr_elem = call_com(uia_ptr, 6, proto_handle, hwnd, ctypes.byref(elem_ptr))
        if hr_elem != 0 or not elem_ptr.value:
            return ""
        
        # Get RawViewWalker (offset 16)
        proto_walker = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        walker_ptr = ctypes.c_void_p()
        hr_walk = call_com(uia_ptr, 16, proto_walker, ctypes.byref(walker_ptr))
        if hr_walk != 0 or not walker_ptr.value:
            call_com(elem_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
            return ""
        
        proto_child = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        
        # Simple depth-first search for browser URL
        def search_element(curr, depth=0):
            if depth > 12:  # Safe limit
                return None
            
            ctype = get_element_control_type(curr)
            name = get_element_name(curr)
            cls_name = get_element_class_name(curr)
            
            if ctype == 50004:
                val = get_element_value(curr)
                if val:
                    # Check for standard URL heuristics
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
            
            # Get first child
            child = ctypes.c_void_p()
            hr_child = call_com(walker_ptr, 3, proto_child, curr, ctypes.byref(child))
            while hr_child == 0 and child.value:
                res = search_element(child, depth + 1)
                if res:
                    call_com(child, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
                    return res
                
                # Sibling
                sib = ctypes.c_void_p()
                hr_sib = call_com(walker_ptr, 4, proto_child, child, ctypes.byref(sib))
                call_com(child, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
                child = sib
                hr_child = hr_sib
                
            return None

        url = search_element(elem_ptr)
        
        # Cleanup walker and element
        call_com(walker_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
        call_com(elem_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
        
        if url:
            if not (url.startswith("http://") or url.startswith("https://")):
                url = "https://" + url
            return url
            
    except Exception as e:
        import logging
        logging.error(f"Error in get_browser_url: {e}")
    finally:
        if uia_ptr.value:
            call_com(uia_ptr, 2, ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p))
        ctypes.windll.ole32.CoUninitialize()
        
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

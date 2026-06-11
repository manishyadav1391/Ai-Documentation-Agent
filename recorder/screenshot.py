import pyautogui
from PIL import Image, ImageDraw, ImageFont
import win32gui
import time
import logging
import win32process
import win32api
import os
import ctypes

def is_browser_window(hwnd):
    if not hwnd:
        return False
    try:
        class_name = win32gui.GetClassName(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        exe_path = win32process.GetModuleFileNameEx(handle, 0)
        win32api.CloseHandle(handle)
        proc_name = os.path.basename(exe_path).lower()
        
        BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "arc.exe", "vivaldi.exe"}
        return proc_name in BROWSER_PROCESSES or class_name in ("Chrome_WidgetWin_1", "MozillaWindowClass")
    except Exception as e:
        logging.debug(f"Error classifying browser for hwnd {hwnd}: {e}")
        return False

def get_browser_crop_height(hwnd):
    try:
        placement = win32gui.GetWindowPlacement(hwnd)
        is_maximized = placement[1] == 3
    except Exception:
        is_maximized = False
        
    try:
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
        scale = dpi / 96.0
    except Exception:
        scale = 1.0
        
    base_height = 143
    if is_maximized:
        base_height -= 8
        
    return int(base_height * scale)


def get_text_size(text, font, draw):
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    elif hasattr(draw, "textsize"):
        return draw.textsize(text, font=font)
    else:
        return len(text) * 8, 15

def load_fonts():
    try:
        font_step = ImageFont.truetype("segoeuib.ttf", 13)
        font_action = ImageFont.truetype("segoeui.ttf", 15)
        return font_step, font_action
    except IOError:
        try:
            font_step = ImageFont.truetype("arialbd.ttf", 13)
            font_action = ImageFont.truetype("arial.ttf", 15)
            return font_step, font_action
        except IOError:
            default_font = ImageFont.load_default()
            return default_font, default_font

def capture_screenshot(filename, click_coords=None, highlight_rect=None, step_no=None, action_label=None, delay=0.04):
    """
    Captures a screenshot, crops to the active window (excluding taskbar/other apps), 
    and applies premium visual highlights:
    - Waits for `delay` seconds before capture to ensure UI render is complete.
    - Crops screenshot to the active/foreground window if possible.
    - Draws a red rectangle with semi-transparent red fill around highlight_rect (if provided).
    - Otherwise, draws a red circle with semi-transparent fill around click_coords (if provided).
    - Overlays a dark card with "STEP X" and action label in the window's top-left corner.
    """
    logging.info(
        f"capture_screenshot() "
        f"click_coords={click_coords}, "
        f"highlight_rect={highlight_rect}, "
        f"step_no={step_no}, "
        f"action_label={action_label}"
    )
    logging.info(
    f"SCREENSHOT RECEIVED RECT = {highlight_rect}"
)
    try:
        # 1. Delay before screenshot to ensure page renders
        if delay and delay > 0:
            time.sleep(delay)
            
        # 2. Capture full screen first
        screenshot = pyautogui.screenshot()
        
        # 3. Determine active window rect for cropping and overlay positioning
        hwnd = win32gui.GetForegroundWindow()
        window_rect = None
        is_browser = False
        crop_height = 0
        if hwnd:
            try:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                # Clamp coordinates to screen boundaries
                left = max(0, left)
                top = max(0, top)
                right = min(screenshot.width, right)
                bottom = min(screenshot.height, bottom)
                if right > left and bottom > top:
                    window_rect = (left, top, right, bottom)
                
                is_browser = is_browser_window(hwnd)
                if is_browser:
                    crop_height = get_browser_crop_height(hwnd)
            except Exception as w_err:
                logging.debug(f"Could not get window rect for hwnd {hwnd}: {w_err}")

        # 4. Prepare RGBA drawing overlay for transparency support
        screenshot_rgba = screenshot.convert("RGBA")
        overlay = Image.new("RGBA", screenshot_rgba.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        drawn = False
        # draw_overlay.rectangle(
        #     [100, 100, 400, 200],
        #     outline=(255, 0, 0, 255),
        #     width=8
        # )

        drawn = False
        
        # 5. Draw bounding rectangle of UI element with semi-transparent fill
        if highlight_rect:
            left_el = highlight_rect.get("left")
            top_el = highlight_rect.get("top")
            right_el = highlight_rect.get("right")
            bottom_el = highlight_rect.get("bottom")
            
            if (left_el is not None and top_el is not None and right_el is not None and bottom_el is not None and 
                right_el > left_el and bottom_el > top_el):
                # Red outline (width=4) and semi-transparent red fill (alpha=40 / 15% opacity)
                draw_overlay.rectangle([left_el, top_el, right_el, bottom_el], fill=(255, 0, 0, 40), outline=(255, 0, 0, 255), width=4)
                drawn = True
                
        # 6. Fallback to click coordinate dot/circle
        if not drawn and click_coords:
            x, y = click_coords
            r = 12
            # Draw outer circle with semi-transparent fill
            draw_overlay.ellipse([x - r, y - r, x + r, y + r], fill=(255, 0, 0, 40), outline=(255, 0, 0, 255), width=4)
            # Draw solid inner dot
            draw_overlay.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 0, 0, 255))
            
        # 7. Draw step number and action overlay card (Removed as requested)
        # if step_no is not None:
        #     font_step, font_action = load_fonts()
        #     step_text = f"STEP {step_no}"
        #     action_text = action_label if action_label else ""
        #     
        #     # Determine card width and height dynamically based on text
        #     step_w, step_h = get_text_size(step_text, font_step, draw_overlay)
        #     action_w, action_h = get_text_size(action_text, font_action, draw_overlay) if action_text else (0, 0)
        #     
        #     box_w = max(step_w, action_w) + 24
        #     box_h = step_h + action_h + 20 if action_text else step_h + 16
        #     
        #     # Position the card at the top-left of the target capture area
        #     card_x = (window_rect[0] if window_rect else 0) + 15
        #     card_y = (window_rect[1] if window_rect else 0) + crop_height + 15
        #     
        #     # Draw semi-transparent dark gray card background (opacity 220/255)
        #     if hasattr(draw_overlay, "rounded_rectangle"):
        #         draw_overlay.rounded_rectangle([card_x, card_y, card_x + box_w, card_y + box_h], radius=6, fill=(30, 30, 30, 220))
        #     else:
        #         draw_overlay.rectangle([card_x, card_y, card_x + box_w, card_y + box_h], fill=(30, 30, 30, 220))
        #         
        #     # Draw Step text (Cyan)
        #     draw_overlay.text((card_x + 12, card_y + 8), step_text, font=font_step, fill=(0, 220, 255, 255))
        #     # Draw Action text if available (White)
        #     if action_text:
        #         draw_overlay.text((card_x + 12, card_y + 8 + step_h + 4), action_text, font=font_action, fill=(255, 255, 255, 255))

        # 8. Blend the overlay onto the screenshot and convert back to RGB
        screenshot_rgba = Image.alpha_composite(screenshot_rgba, overlay)
        screenshot = screenshot_rgba.convert("RGB")
        
        # 9. Crop image to foreground window rect
        if window_rect:
            crop_left = window_rect[0]
            crop_top = min(window_rect[1] + crop_height, window_rect[3] - 1)
            crop_right = window_rect[2]
            crop_bottom = window_rect[3]
            
            if crop_right > crop_left and crop_bottom > crop_top:
                screenshot = screenshot.crop((crop_left, crop_top, crop_right, crop_bottom))
            else:
                screenshot = screenshot.crop(window_rect)
            
        screenshot.save(filename)
        logging.info(f"Saved highlighted and cropped active window screenshot to {filename}")
        
    except Exception as e:
        logging.error(f"Error capturing screenshot: {e}")
        # Try a basic fallback capture without drawing/cropping in case of failure
        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            logging.info(f"Saved fallback raw screenshot to {filename}")
        except Exception as fallback_err:
            logging.critical(f"Failed to capture fallback screenshot: {fallback_err}")


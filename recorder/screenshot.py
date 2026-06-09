import pyautogui
from PIL import ImageDraw
import logging

def capture_screenshot(filename, click_coords=None, highlight_rect=None):
    """
    Captures a full screen screenshot and applies highlights:
    - Draws a red rectangle around highlight_rect (if provided).
    - Otherwise, draws a red circle around click_coords (if provided).
    """
    try:
        screenshot = pyautogui.screenshot()
        draw = ImageDraw.Draw(screenshot)
        drawn = False
        
        # 1. Attempt to draw bounding rectangle of UI element
        if highlight_rect:
            left = highlight_rect.get("left")
            top = highlight_rect.get("top")
            right = highlight_rect.get("right")
            bottom = highlight_rect.get("bottom")
            
            # Simple boundary check
            if (left is not None and top is not None and right is not None and bottom is not None and 
                right > left and bottom > top):
                # Draw outer boundary
                draw.rectangle([left, top, right, bottom], outline="red", width=4)
                drawn = True
                
        # 2. Fallback to click coordinate dot/circle
        if not drawn and click_coords:
            x, y = click_coords
            r = 12
            # Draw circle outline
            draw.ellipse([x - r, y - r, x + r, y + r], outline="red", width=4)
            # Draw tiny inner dot
            draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill="red")
            
        screenshot.save(filename)
        logging.info(f"Saved highlighted screenshot to {filename}")
        
    except Exception as e:
        logging.error(f"Error capturing screenshot: {e}")
        # Try a basic fallback capture without drawing in case drawing failed
        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            logging.info(f"Saved fallback raw screenshot to {filename}")
        except Exception as fallback_err:
            logging.critical(f"Failed to capture fallback screenshot: {fallback_err}")

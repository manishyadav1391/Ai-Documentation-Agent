"""Quick rect validation test - writes output to a file to avoid encoding issues."""
import json
import time
from pynput import mouse
from recorder.uia_helper import get_element_at
from recorder.window_tracker import get_active_window_info

results = []
click_count = [0]

def on_click(x, y, button, pressed):
    if pressed and button == mouse.Button.left:
        click_count[0] += 1
        
        elem = get_element_at(x, y)
        win = get_active_window_info()
        
        result = {
            "click": click_count[0],
            "x": x, "y": y,
            "window": win.get("title", "?")[:50],
            "element": elem if elem else "None",
        }
        results.append(result)
        
        if click_count[0] >= 3:
            return False

print("Click on 3 elements in 3 seconds...")
time.sleep(3)

with mouse.Listener(on_click=on_click) as listener:
    listener.join()

with open("debug_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False, default=str)

print(f"Done! {len(results)} clicks saved to debug_output.json")

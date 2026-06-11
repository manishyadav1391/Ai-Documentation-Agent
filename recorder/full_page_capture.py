import time
import logging
import win32gui
import pyautogui
import imagehash

from PIL import Image


def _get_browser_window_rect(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    return {
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top
    }


def _capture_browser_viewport(hwnd):
    rect = _get_browser_window_rect(hwnd)

    img = pyautogui.screenshot(
        region=(
            rect["left"],
            rect["top"],
            rect["width"],
            rect["height"]
        )
    )

    return img


def _images_are_same(img1, img2, threshold=2):
    try:
        h1 = imagehash.average_hash(img1)
        h2 = imagehash.average_hash(img2)

        diff = h1 - h2

        return diff <= threshold

    except Exception:
        return False


def _remove_overlap(prev_img, curr_img, search_height=300):
    """
    Removes duplicated area between screenshots.

    This is intentionally simple and fast.
    """

    try:
        width = prev_img.width

        prev_crop = prev_img.crop(
            (
                0,
                prev_img.height - search_height,
                width,
                prev_img.height
            )
        )

        prev_hash = imagehash.average_hash(prev_crop)

        best_y = 0
        best_diff = 999

        step = 20

        for y in range(0, min(search_height, curr_img.height - search_height), step):

            curr_crop = curr_img.crop(
                (
                    0,
                    y,
                    width,
                    y + search_height
                )
            )

            curr_hash = imagehash.average_hash(curr_crop)

            diff = prev_hash - curr_hash

            if diff < best_diff:
                best_diff = diff
                best_y = y

        return curr_img.crop(
            (
                0,
                best_y,
                curr_img.width,
                curr_img.height
            )
        )

    except Exception:
        return curr_img


def capture_full_page(hwnd, output_file):
    """
    Captures a full scrollable browser page
    using the currently active browser.

    Parameters
    ----------
    hwnd : int
        Browser window handle

    output_file : str
        Final stitched PNG path
    """

    logging.info("Starting full page capture")

    try:

        win32gui.SetForegroundWindow(hwnd)

    except Exception:
        pass

    time.sleep(0.5)

    screenshots = []

    try:

        pyautogui.hotkey("ctrl", "home")

        time.sleep(1)

    except Exception:
        pass

    first_img = _capture_browser_viewport(hwnd)

    screenshots.append(first_img)

    previous_img = first_img

    max_pages = 50

    for page_no in range(max_pages):

        pyautogui.press("pagedown")

        time.sleep(0.8)

        current_img = _capture_browser_viewport(hwnd)

        if _images_are_same(previous_img, current_img):

            logging.info(
                f"Reached page bottom after {page_no + 1} scrolls"
            )

            break

        screenshots.append(current_img)

        previous_img = current_img

    try:

        pyautogui.hotkey("ctrl", "home")

    except Exception:
        pass

    processed = [screenshots[0]]

    for i in range(1, len(screenshots)):

        processed.append(
            _remove_overlap(
                processed[-1],
                screenshots[i]
            )
        )

    total_height = sum(img.height for img in processed)

    width = processed[0].width

    final_image = Image.new(
        "RGB",
        (width, total_height),
        (255, 255, 255)
    )

    y_offset = 0

    for img in processed:

        final_image.paste(img, (0, y_offset))

        y_offset += img.height

    final_image.save(output_file)

    logging.info(
        f"Full page capture saved: {output_file}"
    )

    return output_file
import time
import logging
import win32gui
import pyautogui
import mss
import cv2
import numpy as np

from PIL import Image
from .screenshot import is_browser_window, get_browser_crop_height


SCROLL_AMOUNT = -1200
MAX_SCROLLS = 50
SCROLL_DELAY = 0.8


def get_window_rect(hwnd):

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    return {
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top
    }


def capture_window(hwnd, rect=None):

    if rect is None:
        rect = get_window_rect(hwnd)

    left = rect["left"]
    top = rect["top"]
    width = rect["width"]
    height = rect["height"]

    # Crop the browser header (tabs, omnibox, bookmarks) and bottom window border
    if is_browser_window(hwnd):
        crop_height = get_browser_crop_height(hwnd)
        top += crop_height
        height -= crop_height
        # Exclude standard bottom border / taskbar overlaps
        height -= 8

    with mss.mss() as sct:

        img = sct.grab({
            "left": left,
            "top": top,
            "width": width,
            "height": height
        })

        return Image.fromarray(
            np.array(img)[:, :, :3]
        )


def find_overlap(prev_img, curr_img):

    # Ensure same width to prevent template dimensions mismatch
    w = min(prev_img.width, curr_img.width)
    if prev_img.width != w:
        left = (prev_img.width - w) // 2
        prev_img = prev_img.crop((left, 0, left + w, prev_img.height))
    if curr_img.width != w:
        left = (curr_img.width - w) // 2
        curr_img = curr_img.crop((left, 0, left + w, curr_img.height))

    prev_gray = cv2.cvtColor(
        np.array(prev_img),
        cv2.COLOR_RGB2GRAY
    )

    curr_gray = cv2.cvtColor(
        np.array(curr_img),
        cv2.COLOR_RGB2GRAY
    )

    search_height = min(
        400,
        prev_gray.shape[0] // 2,
        curr_gray.shape[0]
    )

    if search_height <= 0:
        return None

    template = prev_gray[
        prev_gray.shape[0] - search_height:
    ]

    # Double check template dimensions vs search image dimensions
    if template.shape[0] > curr_gray.shape[0] or template.shape[1] > curr_gray.shape[1]:
        return None

    result = cv2.matchTemplate(
        curr_gray,
        template,
        cv2.TM_CCOEFF_NORMED
    )

    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < 0.85:
        return None

    return max_loc[1]


def remove_overlap(prev_img, curr_img):

    overlap_y = find_overlap(
        prev_img,
        curr_img
    )

    if overlap_y is None:
        return curr_img

    # Correct crop start: offset overlap_y by the template height to avoid duplicate seams
    search_height = min(
        400,
        prev_img.height // 2,
        curr_img.height
    )
    crop_start_y = overlap_y + search_height

    return curr_img.crop(
        (
            0,
            crop_start_y,
            curr_img.width,
            curr_img.height
        )
    )


def reached_bottom(prev_img, curr_img):

    overlap_y = find_overlap(
        prev_img,
        curr_img
    )

    if overlap_y is None:
        return False

    # Also check if overlap_y is close to prev_img.height - search_height (meaning no scroll occurred)
    search_height = min(
        400,
        prev_img.height // 2,
        curr_img.height
    )
    no_scroll_threshold = prev_img.height - search_height - 10

    if overlap_y >= no_scroll_threshold:
        return True

    if overlap_y < 10:
        return True

    return False


def scroll_page(hwnd, rect=None):

    if rect is None:
        rect = get_window_rect(hwnd)

    # Position mouse near the right side of the window to avoid inner scroll containers (like sidebars/chats)
    center_x = max(
        rect["left"] + rect["width"] // 2,
        rect["left"] + rect["width"] - 80
    )
    center_y = rect["top"] + rect["height"] // 2

    pyautogui.moveTo(
        center_x,
        center_y
    )

    pyautogui.scroll(
        SCROLL_AMOUNT
    )


def capture_full_page(hwnd, output_file):

    logging.info(
        "Starting OpenCV full-page capture"
    )

    try:
        win32gui.SetForegroundWindow(hwnd)
    except:
        pass

    time.sleep(1)

    rect = get_window_rect(hwnd)

    scroll_x = max(
        rect["left"] + rect["width"] // 2,
        rect["left"] + rect["width"] - 80
    )
    pyautogui.moveTo(
        scroll_x,
        rect["top"] + rect["height"] // 2
    )

    pyautogui.hotkey(
        "ctrl",
        "home"
    )

    time.sleep(1)

    images = []

    first = capture_window(hwnd, rect)

    images.append(first)

    previous = first

    for i in range(MAX_SCROLLS):

        scroll_page(hwnd, rect)

        time.sleep(SCROLL_DELAY)

        current = capture_window(hwnd, rect)

        if reached_bottom(
            previous,
            current
        ):
            logging.info(
                f"Bottom reached after {i+1} scrolls"
            )
            break

        images.append(current)

        previous = current

    stitched = [images[0]]

    # For subsequent images, compare with the previous FULL uncropped screenshot
    for idx in range(1, len(images)):
        overlap_y = find_overlap(images[idx - 1], images[idx])
        if overlap_y is None:
            # If no overlap detected, append the image as is
            stitched.append(images[idx])
        else:
            # Correct crop start: offset overlap_y by the template height to avoid duplicate seams
            search_height = min(
                400,
                images[idx - 1].height // 2,
                images[idx].height
            )
            crop_start_y = overlap_y + search_height

            # Crop the current image to remove the overlap area
            cropped = images[idx].crop(
                (
                    0,
                    crop_start_y,
                    images[idx].width,
                    images[idx].height
                )
            )
            stitched.append(cropped)

    total_height = sum(
        img.height
        for img in stitched
    )

    width = stitched[0].width

    final_img = Image.new(
        "RGB",
        (width, total_height)
    )

    y = 0

    for img in stitched:

        final_img.paste(
            img,
            (0, y)
        )

        y += img.height

    final_img.save(output_file)

    logging.info(
        f"Saved {output_file}"
    )

    return output_file
import os
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def capture_full_page(url, filename):

    chrome_options = Options()

    chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=chrome_options)

    try:

        driver.get(url)
        
        # Scroll to bottom and back up to trigger lazy-loading of images/elements
        import time
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

        metrics = driver.execute_cdp_cmd(
            "Page.getLayoutMetrics",
            {}
        )

        width = int(
            metrics["contentSize"]["width"]
        )

        height = int(
            metrics["contentSize"]["height"]
        )

        screenshot = driver.execute_cdp_cmd(
            "Page.captureScreenshot",
            {
                "format": "png",
                "captureBeyondViewport": True,
                "clip": {
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                    "scale": 1
                }
            }
        )

        with open(filename, "wb") as f:
            f.write(
                base64.b64decode(
                    screenshot["data"]
                )
            )

        return filename

    finally:
        driver.quit()
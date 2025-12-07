import uiautomator2 as u2
import json
import time
import os
import logging
from typing import Dict, List

from personal_icon_detector import PersonalIconDetector
from setting_icon_detector import GeminiSegmentationAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleNavigator:
    def __init__(self, device_serial: str, app_package: str, gemini_api_key: str):
        self.device = u2.connect(device_serial)
        self.app_package = app_package
        self.gemini_api_key = gemini_api_key
        self.screen_width, self.screen_height = self.device.window_size()

    def capture_screenshot(self) -> bytes:
        temp_path = "temp_screenshot.png"
        try:
            self.device.screenshot(temp_path)
            with open(temp_path, "rb") as f:
                data = f.read()
            os.remove(temp_path)
            return data
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {str(e)}")
            raise

    def normalize_bounds(self, bbox: List[int]) -> str:
        norm_bbox = [
            bbox[1] / 1000,
            bbox[0] / 1000,
            bbox[3] / 1000,
            bbox[2] / 1000
        ]
        return f"[{norm_bbox[0]:.3f},{norm_bbox[1]:.3f}][{norm_bbox[2]:.3f},{norm_bbox[3]:.3f}]"

    def get_click_coordinates(self, bbox: List[int]) -> (int, int):
        norm_x1 = bbox[1] / 1000
        norm_y1 = bbox[0] / 1000
        norm_x2 = bbox[3] / 1000
        norm_y2 = bbox[2] / 1000

        center_x = int((norm_x1 + norm_x2) / 2 * self.screen_width)
        center_y = int((norm_y1 + norm_y2) / 2 * self.screen_height)
        return center_x, center_y

    def navigate(self) -> List[Dict]:
        result = []
        try:
            os.makedirs("results", exist_ok=True)

            logger.info("Detecting personal icon...")
            personal_detector = PersonalIconDetector(self.gemini_api_key)
            screenshot = self.capture_screenshot()
            personal_result = personal_detector.detect_ui_elements(screenshot)

            if personal_result:
                logger.info(f"Personal icon detected: {personal_result}")
                result.append({
                    "bounds": self.normalize_bounds(personal_result["box_2d"]),
                    "text": "我的"
                })

                center_x, center_y = self.get_click_coordinates(personal_result["box_2d"])
                logger.info(f"Clicking personal icon: ({center_x}, {center_y})")
                self.device.click(center_x, center_y)
                time.sleep(2)

                post_click_screenshot = self.capture_screenshot()
                with open(f"results/personal_clicked_{int(time.time())}.png", "wb") as f:
                    f.write(post_click_screenshot)

                time.sleep(2)

            logger.info("Detecting setting icon...")
            setting_detector = GeminiSegmentationAPI(self.gemini_api_key)
            screenshot = self.capture_screenshot()
            setting_result = setting_detector.detect_ui_elements(screenshot)

            if setting_result:
                logger.info(f"Setting icon detected: {setting_result}")
                result.append({
                    "bounds": self.normalize_bounds(setting_result["box_2d"]),
                    "text": "设置"
                })

                center_x, center_y = self.get_click_coordinates(setting_result["box_2d"])
                logger.info(f"Clicking setting icon: ({center_x}, {center_y})")
                self.device.click(center_x, center_y)
                time.sleep(2)

                post_click_screenshot = self.capture_screenshot()
                with open(f"results/setting_clicked_{int(time.time())}.png", "wb") as f:
                    f.write(post_click_screenshot)

            return result

        except Exception as e:
            logger.error(f"Navigation error: {str(e)}")
            return result

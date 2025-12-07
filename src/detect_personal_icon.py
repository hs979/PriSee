import uiautomator2 as u2
from PIL import Image, ImageDraw
import io
import json
import os
import time
import base64
from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 配置参数
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 网络请求配置
MAX_RETRIES = 2
BACKOFF_FACTOR = 1
TIMEOUT = 300


class DetectionResult(BaseModel):
    box_2d: List[int]  # [ymin, xmin, ymax, xmax] 比例坐标(0-1000)
    label: str
    mask: str  # base64编码的分割掩码


class PersonalIconDetector:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.total_prompt_tokens = 0
        self.total_candidates_tokens = 0
        self.total_total_tokens = 0
        self.api_url = f"{GEMINI_API_BASE}/v1/chat/completions"
        self.model = "gemini-2.5-pro-exp-03-25"
        # self.model = "gemini-2.5-flash-preview-05-20"
        # 配置会话和重试策略
        self.session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def detect_personal_icon(self, image_bytes: bytes) -> Optional[Tuple[List[int], str]]:
        """
        检测个人中心图标
        返回: (转换后的坐标[x1,y1,x2,y2]原始像素坐标, 标签) 或 None
        """
        prompt = """严格检测手机应用中指向个人中心或"我的"页面的图标或文字元素，要求：
        1. 识别以下类型的元素：
           - 人形图标
           - "我"、"我的"、"个人中心"、"账号"、"更多"等文字

        2. 优先检测屏幕右下角或左上角区域
        3. 元素大小通常在24-48dp范围内
        4. 识别位置优先靠下

        输出格式（仅当找到符合条件的元素时）：
        [{
            "box_2d": [y1,x1,y2,x2],  // 归一化坐标0-1000
            "label": "personal icon/text",  // 必须包含"personal"或"my"
            "mask": "base64encoded..." // 分割掩码
        }]

        如果没有找到相关元素，返回空列表[]"""

        try:
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size
            logger.info(f"Image size: {width}x{height}")

            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 8000,
                "response_format": {"type": "json_object"}
            }

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }

            for attempt in range(MAX_RETRIES):
                try:
                    logger.info(f" 尝试 {attempt + 1}: 发送API请求到 {self.api_url}")
                    response = self.session.post(
                        self.api_url,
                        headers=headers,
                        json=payload,
                        timeout=TIMEOUT
                    )

                    response.raise_for_status()

                    try:
                        response_data = response.json()
                    except json.JSONDecodeError:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(BACKOFF_FACTOR * (attempt + 1))
                            continue
                        return None

                    if "error" in response_data:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(BACKOFF_FACTOR * (attempt + 1))
                            continue
                        return None

                    content = None
                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        content = response_data["choices"][0].get("message", {}).get("content", "")
                    elif "message" in response_data:
                        content = response_data["message"]

                    if not content:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(BACKOFF_FACTOR * (attempt + 1))
                            continue
                        return None

                    if content.startswith('```json'):
                        content = content[7:-3].strip()
                    elif content.startswith('```'):
                        content = content[3:-3].strip()

                    try:
                        parsed_content = json.loads(content)
                        if isinstance(parsed_content, list):
                            detections = parsed_content
                        elif isinstance(parsed_content, dict):
                            detections = parsed_content.get("detections", [])
                            if not detections:
                                detections = parsed_content.get("elements", [])
                        else:
                            detections = []

                        personal_elements = [
                            item for item in detections
                            if isinstance(item, dict) and
                               any(keyword in item.get("label", "").lower()
                                   for keyword in ["personal", "my", "profile", "account", "我的", "个人"])
                        ]

                        if not personal_elements:
                            return None

                        bbox = personal_elements[0]["box_2d"]
                        pixel_bbox = [
                            int(bbox[1] * width / 1000),
                            int(bbox[0] * height / 1000),
                            int(bbox[3] * width / 1000),
                            int(bbox[2] * height / 1000)
                        ]
                        logger.info(f"Detected personal icon at {pixel_bbox}")
                        return pixel_bbox, personal_elements[0]["label"]

                    except json.JSONDecodeError:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(BACKOFF_FACTOR * (attempt + 1))
                            continue
                        return None

                except requests.exceptions.RequestException:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(BACKOFF_FACTOR * (attempt + 1))
                        continue
                    return None
                except Exception:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(BACKOFF_FACTOR * (attempt + 1))
                        continue
                    return None

            return None

        except Exception as e:
            logger.error(f"Personal icon detection failed: {str(e)}")
            return None


def visualize_detection(image_bytes: bytes, bbox: List[float], label: str, output_path: str):
    """可视化检测结果"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        draw = ImageDraw.Draw(img)

        x1, y1, x2, y2 = bbox
        draw.rectangle([x1, y1, x2, y2], outline="blue", width=3)
        draw.text((x1, y1 - 30), label, fill="blue")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path)
        logger.info(f"Visualization saved to {output_path}")
    except Exception as e:
        logger.error(f"Visualization failed: {str(e)}")


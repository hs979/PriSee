from PIL import Image
import io
import json
import logging
import base64
import requests
from typing import List, Tuple, Optional
from pydantic import BaseModel

from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 配置 Gemini 接口
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE")
GEMINI_MODEL = "gemini-2.5-pro-exp-03-25"
# GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
GEMINI_MAX_TOKENS = 8192

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DetectionResult(BaseModel):
    box_2d: List[int]  # [ymin, xmin, ymax, xmax]
    label: str
    mask: str  # base64编码的掩码图像


class SettingIconDetector:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.total_prompt_tokens = 0
        self.total_candidates_tokens = 0
        self.total_total_tokens = 0

    def detect_setting_icon(self, image_bytes: bytes) -> Optional[Tuple[List[int], str]]:
        prompt = """识别手机应用中的“设置”图标或按钮，要求：
        1. 优先识别带有“齿轮形状”、“六边形”或写有“设置”字样的按钮；
        2. 位置通常在右上角，但不限于此；
        3. 可以是图标+文字组合或单独图标；
        4. 如果出现"设置"字样，直接输出"设置"字样所在的区域及标签信息（见下方格式），否则输出设置图标的区域及标签信息（同下方格式）

        输出格式：
        [{
            "box_2d": [y1,x1,y2,x2],
            "label": "setting icon",
            "mask": "base64encoded..."
        }]

        如未识别则返回 []
        """

        try:
            # 图片编码为 base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            payload = json.dumps({
                "model": GEMINI_MODEL,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"}
                             }
                        ]
                    }
                ],
                "temperature": 0.9,
                "max_tokens": GEMINI_MAX_TOKENS,
                "response_format": {"type": "json_object"}
            })

            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }

            response = requests.post(
                f"{GEMINI_API_BASE}/v1/chat/completions",
                headers=headers,
                data=payload
            )

            response_data = response.json()
            if 'usage' in response_data:
                usage = response_data['usage']
                self.total_prompt_tokens += usage.get('prompt_tokens', 0)
                self.total_candidates_tokens += usage.get('completion_tokens', 0)
                self.total_total_tokens += usage.get('total_tokens', 0)

            if 'choices' not in response_data or not response_data['choices']:
                logger.warning("No choices in response")
                return None

            content = response_data['choices'][0]['message']['content']
            if not content:
                logger.warning("Empty content in Gemini response")
                return None

            try:
                detections = json.loads(content)
                if not isinstance(detections, list):
                    logger.warning("Response is not a list")
                    return None

                setting_icons = [
                    d for d in detections
                    if "setting" in d.get("label", "").lower()
                ]

                if not setting_icons:
                    logger.info("No setting icon detected")
                    return None

                image = Image.open(io.BytesIO(image_bytes))
                width, height = image.size
                box = setting_icons[0]["box_2d"]
                pixel_box = [
                    int(box[1] * width / 1000),
                    int(box[0] * height / 1000),
                    int(box[3] * width / 1000),
                    int(box[2] * height / 1000),
                ]
                label = setting_icons[0]["label"]
                logger.info(f"Detected setting icon at {pixel_box}")
                return pixel_box, label

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response JSON: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"API call failed: {str(e)}")
            return None



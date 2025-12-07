import uiautomator2 as u2
from PIL import Image, ImageDraw
import io
import json
import os
import re
import time
import base64
import requests
from typing import List, Dict, Optional
from pydantic import BaseModel
from io import BytesIO


class PersonalIconDetector:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.total_prompt_tokens = 0
        self.total_candidates_tokens = 0
        self.total_total_tokens = 0
        self.model = "gemini-2.5-flash-preview-05-20"
        self.api_base = "http://jeniya.cn"

    def detect_ui_elements(self, image_bytes: bytes) -> Optional[Dict]:
        prompt = """请你严格按照以下指示步骤工作：
        你需要完成的工作是：
        （1）严格检测手机应用中指向个人中心或"我的"页面的图标或文字元素
        （2）返回: (转换后的坐标[x1,y1,x2,y2]原始像素坐标, 标签) 或 None
        ### 你的思考过程（此部分仅用于解释，不要放入JSON） ###
        1. 识别以下类型的元素：
           - 人形图标
           - "我"、"我的"、"个人中心"、"账号"、"更多"等文字（绝大多数情况下都是有文字的，没有文字可能性特别小）
           - 文字的描述不仅限于此，你应该结合你自己的思考判断
        2. 优先检测屏幕右下角或左上角区域(右下角的概率遥遥领先)
        3. 评估每个候选图标的特征
        4.你获取坐标的时候尽可能缩小你的获取范围（当然，你获取的范围也不能过小，要包含足够的要素），不然可能让最终的检测结果框选到太多空白区域，造成点击错误。
        5.还有一点，你记住，一般而言这类图标在app页面导航栏。
        6. 如果找到了，你就跳至输出json的逻辑；如果没找到你认为正确的个人中心图标，那就返回空的json。
        ### 你必须输出的JSON数据 ###
        [{
            "box_2d": [y1,x1,y2,x2],
            "label": "personal icon/text"
        }]
        请先严格按照思考过程进行思考（你的思考过程也要输出！），然后输出正确的JSON数据。"""

        def encode_compressed_image(image_bytes: bytes, quality=20) -> str:
            with Image.open(io.BytesIO(image_bytes)) as img:
                buffered = BytesIO()
                img.save(buffered, format="PNG", quality=quality)
                return base64.b64encode(buffered.getvalue()).decode("utf-8")

        try:
            image_base64 = encode_compressed_image(image_bytes)

            payload = json.dumps({
                "model": self.model,
                "stream": True,
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
                "temperature": 0.2,
                "max_tokens": 8000
            })

            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }

            full_content = ""
            with requests.post(
                    f"{self.api_base}/v1/chat/completions",
                    headers=headers,
                    data=payload,
                    timeout=100,
                    stream=True
            ) as response:
                if response.status_code != 200:
                    return None

                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data:'):
                            json_str = line_str[5:].strip()
                            if json_str == "[DONE]":
                                continue
                            try:
                                chunk_data = json.loads(json_str)
                                if 'choices' in chunk_data and chunk_data['choices']:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    full_content += content
                            except json.JSONDecodeError:
                                pass

            json_match = re.search(r"```json\s*([\s\S]+?)\s*```", full_content)

            if not json_match:
                return None

            json_str = json_match.group(1).strip()

            try:
                detections = json.loads(json_str)
                if detections and isinstance(detections, list) and len(detections) > 0:
                    return detections[0]
                return None
            except Exception:
                return None

        except Exception:
            return None
# rough_position_personal_icon.py
from PIL import Image, ImageDraw
import io
import json
import os
import base64
import requests
import logging
from typing import Dict, Optional

from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 配置参数
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoarsePersonalIconDetector:
    """粗定位：视觉初步识别个人中心图标区域"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "gemini-2.5-pro"

    def detect_personal_region(self, image_bytes: bytes) -> Optional[Dict]:
        """
        粗定位：识别个人中心图标的大致方位区域
        返回区域信息：{region: "bottom_right", confidence: 0.9, hint_bbox: [x1,y1,x2,y2]}
        """
        prompt = """
        【任务说明】
       你是一个专业的UI界面分析助手，需要从手机应用截图中识别"个人中心"或"我的"图标的大致方位区域。

【分析要求】
1. 仔细观察整个界面，寻找以下类型的个人中心图标：
   - 人形图标（绝大部分的样式是头部+半身）
   - 用户头像图标（圆形头像，可能带默认人像）
   - 包含"我"、"我的"、"个人中心"、"账号"、"个人"、"用户"等文字的按钮
   - 可能位于底部导航栏的用户图标

2. 重点关注以下区域（按优先级排序）：
   - 右下角区域（最可能出现，特别是在底部导航栏）
   - 左上角区域（部分应用设计）
   - 右上角区域（可能以头像形式出现）
   - 底部中央区域（少数应用设计）

3. 分析图标的视觉特征：
   - 图标大小：通常在24-48dp范围内
   - 形状：人物轮廓、圆形头像等
   - 位置：通常在屏幕角落或底部导航栏
   - 颜色：可能与主题色一致或形成对比

4. 如果看到任何疑似个人中心图标的元素，请返回对应的区域信息。

【输出格式】
请严格按照以下JSON格式输出，不要包含任何其他文字：

{
  "detected_regions": [
    {
      "region": "bottom_right",  // 区域标识：top_left, top_right, bottom_left, bottom_right, bottom_center
      "confidence": 0.85,        // 置信度 0-1
      "reason": "在右下角发现人形图标，底部导航栏显示'我的'文字，符合个人中心入口特征"//在reason这里，请你尽情地输出你的想法
    }
  ]
}

如果没有检测到任何个人中心图标，返回：
{
  "detected_regions": []
}

请直接输出JSON，不要解释。"""

        try:
            # 压缩图片以减少API负载
            compressed_image_bytes = self._compress_image(image_bytes)
            image_base64 = base64.b64encode(compressed_image_bytes).decode('utf-8')

            payload = {
                "model": self.model,
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
                "temperature": 0.1,
                "max_tokens": 2000
            }

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }

            logger.info("发送个人中心粗定位API请求...")
            response = requests.post(
                f"{GEMINI_API_BASE}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            logger.info(f"API响应状态码: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return None

            response_data = response.json()
            logger.info("成功获取API响应")

            if 'choices' not in response_data or not response_data['choices']:
                logger.error("响应中没有choices字段")
                return None

            content = response_data['choices'][0]['message']['content']
            if not content:
                logger.error("响应内容为空")
                return None

            logger.info(f"原始响应内容: {content}")

            # 尝试清理响应内容，移除可能的markdown标记
            cleaned_content = content.strip()
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.endswith('```'):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()

            logger.info(f"清理后的内容: {cleaned_content}")

            result = json.loads(cleaned_content)
            regions = result.get("detected_regions", [])

            if regions:
                # 选择置信度最高的区域
                best_region = max(regions, key=lambda x: x.get("confidence", 0))
                logger.info(f"粗定位结果: {best_region['region']} (置信度: {best_region['confidence']})")
                logger.info(f"原因: {best_region.get('reason', 'N/A')}")
                return best_region
            else:
                logger.info("未检测到个人中心图标区域")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            logger.error(f"解析的内容: {content if 'content' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"粗定位失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _compress_image(self, image_bytes: bytes, quality: int = 50) -> bytes:
        """压缩图片以减少API负载"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            # 调整图片大小，最大边长为800像素
            max_size = 800
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            # 保存为压缩的JPEG
            output_buffer = io.BytesIO()
            image = image.convert('RGB')  # 转换为RGB以支持JPEG
            image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            return output_buffer.getvalue()
        except Exception as e:
            logger.warning(f"图片压缩失败，使用原图: {str(e)}")
            return image_bytes

    def visualize_coarse_detection(self, image_bytes: bytes, detection: Dict,
                                   output_path: str = "debug/coarse_personal_detection.png"):
        """可视化粗定位结果"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            draw = ImageDraw.Draw(image)
            width, height = image.size

            if "hint_bbox" in detection:
                bbox = detection["hint_bbox"]
                x1 = bbox[1] * width / 1000
                y1 = bbox[0] * height / 1000
                x2 = bbox[3] * width / 1000
                y2 = bbox[2] * height / 1000

                draw.rectangle([x1, y1, x2, y2], outline="green", width=3)
                draw.text((x1, y1 - 20), f"Personal: {detection['region']}", fill="green")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            image.save(output_path)
            logger.info(f"个人中心粗定位可视化已保存: {output_path}")

        except Exception as e:
            logger.error(f"可视化失败: {str(e)}")
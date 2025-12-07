# fine_detector.py
import uiautomator2 as u2
import xml.etree.ElementTree as ET
import json
import base64
import requests
import logging
import re
from typing import List, Dict, Optional

from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_BASE = os.getenv("GEMINI_API_BASE")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FineSettingIconDetector:
    """精定位：结合XML组件数据精确识别设置图标"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "gemini-2.5-pro"

    def extract_clickable_elements(self, d: u2.Device, region: str) -> List[Dict]:
        """
        从指定区域提取可点击的UI组件
        """
        try:
            # 获取界面XML结构
            xml_content = d.dump_hierarchy()
            root = ET.fromstring(xml_content)

            clickable_elements = []
            width, height = d.window_size()

            for elem in root.iter():
                bounds = elem.get('bounds')
                clickable = elem.get('clickable', 'false')
                text = elem.get('text', '')
                desc = elem.get('content-desc', '')
                resource_id = elem.get('resource-id', '')

                if bounds and clickable == 'true':
                    # 解析坐标 [x1,y1][x2,y2]
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())

                        # 归一化坐标
                        norm_x1 = x1 / width
                        norm_y1 = y1 / height
                        norm_x2 = x2 / width
                        norm_y2 = y2 / height

                        # 计算中心点
                        center_x = (norm_x1 + norm_x2) / 2
                        center_y = (norm_y1 + norm_y2) / 2

                        element_info = {
                            "bounds": [x1, y1, x2, y2],
                            "normalized_bounds": [norm_x1, norm_y1, norm_x2, norm_y2],
                            "center": [center_x, center_y],
                            "text": text,
                            "description": desc,
                            "resource_id": resource_id,
                            "class": elem.get('class', ''),
                            "package": elem.get('package', '')
                        }

                        # 根据粗定位区域筛选
                        if self._is_in_region(element_info, region, width, height):
                            clickable_elements.append(element_info)

            logger.info(f"在{region}区域找到{len(clickable_elements)}个可点击元素")
            return clickable_elements

        except Exception as e:
            logger.error(f"提取XML组件失败: {str(e)}")
            return []

    def _is_in_region(self, element: Dict, region: str, screen_width: int, screen_height: int) -> bool:
        """判断元素是否在指定区域内"""
        center_x, center_y = element["center"]

        # 定义各区域的边界（归一化坐标）
        region_map = {
            "top_left": (0, 0, 0.3, 0.2),  # 左上角
            "top_right": (0.7, 0, 1, 0.2),  # 右上角
            "bottom_left": (0, 0.8, 0.3, 1),  # 左下角
            "bottom_right": (0.7, 0.8, 1, 1),  # 右下角
            "top_center": (0.3, 0, 0.7, 0.2)  # 顶部中央
        }

        if region in region_map:
            x1, y1, x2, y2 = region_map[region]
            return x1 <= center_x <= x2 and y1 <= center_y <= y2

        return True  # 如果没有指定区域，返回所有元素

    def fine_detection(self, image_bytes: bytes, clickable_elements: List[Dict], coarse_region: Dict) -> Optional[Dict]:
        """
        精定位：结合截图和XML数据精确识别设置图标

        注意：精定位使用XML中的精确组件坐标，完全忽略粗定位的hint_bbox
        """
        # 构建更详细的组件信息用于提示词
        elements_info = []
        for i, elem in enumerate(clickable_elements):
            elements_info.append({
                "index": i,
                "text": elem.get('text', ''),
                "description": elem.get('description', ''),
                "resource_id": elem.get('resource_id', ''),
                "bounds": elem.get('bounds', []),
                "normalized_bounds": [f"{x:.3f}" for x in elem.get('normalized_bounds', [])],
                "center": [f"{x:.3f}" for x in elem.get('center', [])]
            })

        prompt = f"""【精确定位任务】
你需要在给定的UI组件列表中精确识别出"设置"图标/按钮。

【背景信息】
粗定位提示设置图标可能位于：{coarse_region.get('region', 'unknown')} 区域
粗定位原因：{coarse_region.get('reason', 'N/A')}

【重要说明】
你现在看到的是从APP界面XML结构中提取的精确组件信息，包含每个组件的：
- 精确像素坐标 (bounds字段)
- 文本内容
- 资源ID
- 组件描述

请基于这些精确的组件数据进行分析:

【可用组件数据】
以下是该区域内的所有可点击UI组件信息：

{json.dumps(elements_info, indent=2, ensure_ascii=False)}

【分析任务】
1. 结合截图视觉信息和组件属性，分析每个组件：
   - 文本内容：是否包含"设置"、"Setting"、"配置"、"菜单"、"更多"等关键词
   - 组件描述：content-desc字段是否包含相关描述
   - 资源ID：是否包含"setting"、"config"、"menu"、"more"等标识
   - 视觉特征：在截图中是否显示为齿轮、三点、三条横线等设置相关图标

2. 设置图标的典型特征：
   - 视觉：齿轮图标、三点菜单、三条横线菜单等
   - 文本：包含"设置"、"Setting"等文字
   - 位置：通常在屏幕边缘区域
   - 大小：通常是较小的图标按钮

3. 排除误判：
   - 排除过大或过小的组件（设置图标通常中等大小）
   - 排除明显是其他功能的按钮（返回、主页、搜索、播放等）
   - 优先选择有明确设置相关标识的组件

【输出格式】
请严格按照以下JSON格式输出：

{{
  "selected_element": {{
    "index": 0,  // 在组件列表中的索引
    "confidence": 0.95,  // 最终置信度
    "reason": "该组件资源ID包含'menu'，在截图中显示为三条横线菜单图标，符合设置入口特征"
  }}
}}

如果没有找到合适的设置图标，返回：
{{
  "selected_element": null
}}

请直接输出JSON，不要解释。"""

        try:
            # 压缩图片
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
                "max_tokens": 3000
            }

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }

            logger.info("发送精定位API请求...")
            response = requests.post(
                f"{GEMINI_API_BASE}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
                proxies={"http": None, "https": None}  # 禁用代理
            )

            logger.info(f"精定位API响应状态码: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"精定位API请求失败: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return None

            response_data = response.json()

            if 'choices' not in response_data or not response_data['choices']:
                logger.error("精定位响应中没有choices字段")
                return None

            content = response_data['choices'][0]['message']['content']
            if not content:
                logger.error("精定位响应内容为空")
                return None

            logger.info(f"精定位原始响应内容: {content}")

            # 清理响应内容
            cleaned_content = content.strip()
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.endswith('```'):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()

            logger.info(f"精定位清理后的内容: {cleaned_content}")

            result = json.loads(cleaned_content)
            selected = result.get("selected_element")

            if selected and selected.get("index") is not None:
                element_index = selected["index"]
                if 0 <= element_index < len(clickable_elements):
                    selected_element = clickable_elements[element_index]
                    selected_element["final_confidence"] = selected.get("confidence", 0)
                    selected_element["selection_reason"] = selected.get("reason", "")
                    logger.info(f"精定位成功选择元素 {element_index}: {selected_element.get('text', 'N/A')}")
                    logger.info(f"选择原因: {selected_element['selection_reason']}")
                    return selected_element

            logger.info("精定位未找到合适的设置图标")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"精定位JSON解析失败: {str(e)}")
            logger.error(f"解析的内容: {content if 'content' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"精定位失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _compress_image(self, image_bytes: bytes, quality: int = 50) -> bytes:
        """压缩图片以减少API负载"""
        try:
            from PIL import Image
            import io

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
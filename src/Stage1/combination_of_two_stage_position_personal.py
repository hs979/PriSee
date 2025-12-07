# personal_icon_detection_main.py
import uiautomator2 as u2
import time
import os
import logging
from rough_position_personal_icon import CoarsePersonalIconDetector
from concise_position_personal_icon import FinePersonalIconDetector

from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 配置参数
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEVICE_SERIAL = os.getenv("DEVICE_SERIAL")
APP_PACKAGE = os.getenv("APP_PACKAGE")

# 设置更详细的日志
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PersonalIconDetectionPipeline:
    def __init__(self, api_key: str, device_serial: str):
        try:
            self.device = u2.connect(device_serial)
            logger.info(f" 已连接设备: {device_serial}")
        except Exception as e:
            logger.error(f"  设备连接失败: {str(e)}")
            raise

        self.coarse_detector = CoarsePersonalIconDetector(api_key)
        self.fine_detector = FinePersonalIconDetector(api_key)

    def detect_and_click_personal_icon(self, app_package: str) -> bool:
        """完整的个人中心图标检测和点击流程"""
        screenshot_path = "temp_screenshot_personal.png"

        try:
            # 启动应用
            logger.info(" 启动应用...")
            self.device.app_start(app_package)
            time.sleep(5)

            # 检查应用是否成功启动
            current_app = self.device.app_current()
            logger.info(f"当前应用: {current_app}")

            if current_app['package'] != app_package:
                logger.warning(f"应用可能未成功启动，当前包名: {current_app['package']}")

            # 截图
            logger.info(" 截取屏幕...")
            self.device.screenshot(screenshot_path)

            if not os.path.exists(screenshot_path):
                logger.error("  截图文件未生成")
                return False

            file_size = os.path.getsize(screenshot_path)
            logger.info(f"截图文件大小: {file_size} bytes")

            with open(screenshot_path, "rb") as f:
                screenshot_bytes = f.read()

            # 步骤1: 粗定位
            logger.info(" 阶段1: 粗定位个人中心图标...")
            coarse_result = self.coarse_detector.detect_personal_region(screenshot_bytes)

            if not coarse_result:
                logger.warning("  粗定位未找到个人中心图标区域")
                # 保存截图用于调试
                debug_path = "debug/no_personal_detected.png"
                os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                with open(debug_path, "wb") as f:
                    f.write(screenshot_bytes)
                logger.info(f" 当前界面已保存: {debug_path}")
                return False

            # 可视化粗定位结果
            self.coarse_detector.visualize_coarse_detection(
                screenshot_bytes, coarse_result, "debug/coarse_personal_result.png"
            )

            # 步骤2: 提取区域内的可点击组件
            logger.info(" 阶段2: 提取UI组件...")
            clickable_elements = self.fine_detector.extract_clickable_elements(
                self.device, coarse_result["region"]
            )

            if not clickable_elements:
                logger.warning("  在目标区域未找到可点击组件")
                return False

            logger.info(f"找到 {len(clickable_elements)} 个可点击元素:")
            for i, elem in enumerate(clickable_elements):
                logger.info(f"  {i}: {elem.get('text', 'N/A')} - {elem.get('resource_id', 'N/A')}")

            # 步骤3: 精定位
            logger.info(" 阶段3: 精定位个人中心图标...")
            fine_result = self.fine_detector.fine_detection(
                screenshot_bytes, clickable_elements, coarse_result
            )

            if not fine_result:
                logger.warning("  精定位未找到个人中心图标")
                return False

            # 步骤4: 点击目标元素
            logger.info(" 执行点击...")
            center_x, center_y = fine_result["center"]
            self.device.click(center_x, center_y)

            logger.info(f" 成功点击个人中心图标: {fine_result.get('text', 'N/A')}")
            logger.info(f"   位置: ({center_x:.3f}, {center_y:.3f})")
            logger.info(f"   置信度: {fine_result.get('final_confidence', 0):.2f}")
            logger.info(f"   原因: {fine_result.get('selection_reason', '')}")

            # 等待页面跳转
            time.sleep(3)

            return True

        except Exception as e:
            logger.error(f"  检测流程失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            # 清理临时文件
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                logger.info("🧹 清理临时截图文件")

# 使用示例
if __name__ == "__main__":
    try:
        pipeline = PersonalIconDetectionPipeline(GEMINI_API_KEY, DEVICE_SERIAL)
        success = pipeline.detect_and_click_personal_icon(APP_PACKAGE)

        if success:
            logger.info(" 个人中心图标检测点击流程完成!")
        else:
            logger.info(" 个人中心图标检测点击流程失败")

    except Exception as e:
        logger.error(f"  程序初始化失败: {str(e)}")
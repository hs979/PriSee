# combined_detection_main.py
import uiautomator2 as u2
import time
import os
import json
import logging
from rough_position_setting_icon import CoarseSettingIconDetector
from concise_position_setting_icon import FineSettingIconDetector
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


class CombinedDetectionPipeline:
    def __init__(self, api_key: str, device_serial: str):
        try:
            self.device = u2.connect(device_serial)
            logger.info(f" 已连接设备: {device_serial}")
        except Exception as e:
            logger.error(f"  设备连接失败: {str(e)}")
            raise

        # 初始化两个检测器
        self.setting_coarse_detector = CoarseSettingIconDetector(api_key)
        self.setting_fine_detector = FineSettingIconDetector(api_key)
        self.personal_coarse_detector = CoarsePersonalIconDetector(api_key)
        self.personal_fine_detector = FinePersonalIconDetector(api_key)

        # 存储检测结果和token统计
        self.detection_results = []
        self.token_usage = {
            "personal_coarse": 0,
            "personal_fine": 0,
            "setting_coarse": 0,
            "setting_fine": 0,
            "total": 0
        }

    def _update_token_usage(self, phase: str, tokens: int):
        """更新token使用量"""
        if tokens > 0:
            self.token_usage[phase] += tokens
            self.token_usage["total"] += tokens
            logger.info(f"📊 {phase} 阶段使用了 {tokens} tokens")

    def _detect_and_click_personal_icon(self) -> bool:
        """检测并点击个人中心图标"""
        screenshot_path = "temp_screenshot_personal.png"

        try:
            # 截图
            logger.info(" 截取个人中心检测屏幕...")
            self.device.screenshot(screenshot_path)

            if not os.path.exists(screenshot_path):
                logger.error("  截图文件未生成")
                return False

            with open(screenshot_path, "rb") as f:
                screenshot_bytes = f.read()

            # 步骤1: 粗定位个人中心图标
            logger.info(" 阶段1: 粗定位个人中心图标...")
            coarse_result = self.personal_coarse_detector.detect_personal_region(screenshot_bytes)

            # 尝试获取token使用量（如果检测器支持）
            if hasattr(self.personal_coarse_detector, 'last_token_usage'):
                tokens = self.personal_coarse_detector.last_token_usage
                self._update_token_usage("personal_coarse", tokens)

            if not coarse_result:
                logger.warning("  粗定位未找到个人中心图标区域")
                return False

            # 可视化粗定位结果
            self.personal_coarse_detector.visualize_coarse_detection(
                screenshot_bytes, coarse_result, "debug/coarse_personal_result.png"
            )

            # 步骤2: 提取区域内的可点击组件
            logger.info(" 阶段2: 提取个人中心区域UI组件...")
            clickable_elements = self.personal_fine_detector.extract_clickable_elements(
                self.device, coarse_result["region"]
            )

            if not clickable_elements:
                logger.warning("  在个人中心目标区域未找到可点击组件")
                return False

            logger.info(f"找到 {len(clickable_elements)} 个可点击元素:")
            for i, elem in enumerate(clickable_elements):
                logger.info(f"  {i}: {elem.get('text', 'N/A')} - {elem.get('resource_id', 'N/A')}")

            # 步骤3: 精定位个人中心图标
            logger.info(" 阶段3: 精定位个人中心图标...")
            fine_result = self.personal_fine_detector.fine_detection(
                screenshot_bytes, clickable_elements, coarse_result
            )

            # 尝试获取token使用量（如果检测器支持）
            if hasattr(self.personal_fine_detector, 'last_token_usage'):
                tokens = self.personal_fine_detector.last_token_usage
                self._update_token_usage("personal_fine", tokens)

            if not fine_result:
                logger.warning("  精定位未找到个人中心图标")
                return False

            # 步骤4: 点击目标元素
            logger.info(" 执行个人中心图标点击...")
            center_x, center_y = fine_result["center"]
            self.device.click(center_x, center_y)

            # 记录结果
            bounds_str = f"[{fine_result['normalized_bounds'][0]:.3f},{fine_result['normalized_bounds'][1]:.3f}][{fine_result['normalized_bounds'][2]:.3f},{fine_result['normalized_bounds'][3]:.3f}]"
            self.detection_results.append({
                "bounds": bounds_str,
                "text": fine_result.get('text', '我的')
            })

            logger.info(f" 成功点击个人中心图标: {fine_result.get('text', 'N/A')}")
            logger.info(f"   位置: ({center_x:.3f}, {center_y:.3f})")
            logger.info(f"   边界: {bounds_str}")

            # 等待页面跳转
            time.sleep(3)
            return True

        except Exception as e:
            logger.error(f"  个人中心检测流程失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            # 清理临时文件
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                logger.info("🧹 清理个人中心临时截图文件")

    def _detect_and_click_setting_icon(self) -> bool:
        """检测并点击设置图标"""
        screenshot_path = "temp_screenshot_setting.png"

        try:
            # 截图
            logger.info(" 截取设置检测屏幕...")
            self.device.screenshot(screenshot_path)

            if not os.path.exists(screenshot_path):
                logger.error("  截图文件未生成")
                return False

            with open(screenshot_path, "rb") as f:
                screenshot_bytes = f.read()

            # 步骤1: 粗定位设置图标
            logger.info(" 阶段1: 粗定位设置图标...")
            coarse_result = self.setting_coarse_detector.detect_setting_region(screenshot_bytes)

            # 尝试获取token使用量（如果检测器支持）
            if hasattr(self.setting_coarse_detector, 'last_token_usage'):
                tokens = self.setting_coarse_detector.last_token_usage
                self._update_token_usage("setting_coarse", tokens)

            if not coarse_result:
                logger.warning("  粗定位未找到设置图标区域")
                return False

            # 可视化粗定位结果
            self.setting_coarse_detector.visualize_coarse_detection(
                screenshot_bytes, coarse_result, "debug/coarse_setting_result.png"
            )

            # 步骤2: 提取区域内的可点击组件
            logger.info(" 阶段2: 提取设置区域UI组件...")
            clickable_elements = self.setting_fine_detector.extract_clickable_elements(
                self.device, coarse_result["region"]
            )

            if not clickable_elements:
                logger.warning("  在设置目标区域未找到可点击组件")
                return False

            logger.info(f"找到 {len(clickable_elements)} 个可点击元素:")
            for i, elem in enumerate(clickable_elements):
                logger.info(f"  {i}: {elem.get('text', 'N/A')} - {elem.get('resource_id', 'N/A')}")

            # 步骤3: 精定位设置图标
            logger.info(" 阶段3: 精定位设置图标...")
            fine_result = self.setting_fine_detector.fine_detection(
                screenshot_bytes, clickable_elements, coarse_result
            )

            # 尝试获取token使用量（如果检测器支持）
            if hasattr(self.setting_fine_detector, 'last_token_usage'):
                tokens = self.setting_fine_detector.last_token_usage
                self._update_token_usage("setting_fine", tokens)

            if not fine_result:
                logger.warning("  精定位未找到设置图标")
                return False

            # 步骤4: 点击目标元素
            logger.info(" 执行设置图标点击...")
            center_x, center_y = fine_result["center"]
            self.device.click(center_x, center_y)

            # 记录结果
            bounds_str = f"[{fine_result['normalized_bounds'][0]:.3f},{fine_result['normalized_bounds'][1]:.3f}][{fine_result['normalized_bounds'][2]:.3f},{fine_result['normalized_bounds'][3]:.3f}]"
            self.detection_results.append({
                "bounds": bounds_str,
                "text": fine_result.get('text', '设置')
            })

            logger.info(f" 成功点击设置图标: {fine_result.get('text', 'N/A')}")
            logger.info(f"   位置: ({center_x:.3f}, {center_y:.3f})")
            logger.info(f"   边界: {bounds_str}")

            # 等待页面跳转
            time.sleep(3)
            return True

        except Exception as e:
            logger.error(f"  设置检测流程失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            # 清理临时文件
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                logger.info("清理设置临时截图文件")

    def save_detection_results(self, output_path: str = "detection_results.json"):
        """保存检测结果到JSON文件"""
        try:
            # 添加token使用信息到结果中
            results_with_tokens = {
                "detection_results": self.detection_results,
                "token_usage": self.token_usage,
                "summary": {
                    "total_tokens": self.token_usage["total"],
                    "detection_steps": len(self.detection_results)
                }
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results_with_tokens, f, ensure_ascii=False, indent=2)
            logger.info(f"检测结果已保存到: {output_path}")

            # 在控制台输出token使用摘要
            self._print_token_summary()

        except Exception as e:
            logger.error(f"  保存检测结果失败: {str(e)}")

    def _print_token_summary(self):
        """打印token使用摘要"""
        logger.info("===== TOKEN使用统计 =====")
        logger.info(f"个人中心粗定位: {self.token_usage['personal_coarse']} tokens")
        logger.info(f"个人中心精定位: {self.token_usage['personal_fine']} tokens")
        logger.info(f"设置粗定位: {self.token_usage['setting_coarse']} tokens")
        logger.info(f"设置精定位: {self.token_usage['setting_fine']} tokens")
        logger.info(f"总计使用: {self.token_usage['total']} tokens")
        logger.info("=========================")

    def run_combined_detection(self, app_package: str) -> bool:
        """完整的组合检测流程"""
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

            # 第一步：检测并点击个人中心图标
            logger.info("=" * 50)
            logger.info("开始个人中心图标检测流程")
            logger.info("=" * 50)

            personal_success = self._detect_and_click_personal_icon()

            if not personal_success:
                logger.error("  个人中心图标检测失败，终止流程")
                return False

            # 第二步：检测并点击设置图标（在个人中心页面内）
            logger.info("=" * 50)
            logger.info("开始设置图标检测流程")
            logger.info("=" * 50)

            setting_success = self._detect_and_click_setting_icon()

            if not setting_success:
                logger.error("  设置图标检测失败")

            # 保存检测结果并输出token统计
            self.save_detection_results()

            # 最终token总结
            logger.info(" ===== 检测流程完成 =====")
            self._print_token_summary()

            return personal_success and setting_success

        except Exception as e:
            logger.error(f"  组合检测流程失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False


# 使用示例
if __name__ == "__main__":
    try:
        pipeline = CombinedDetectionPipeline(GEMINI_API_KEY, DEVICE_SERIAL)
        success = pipeline.run_combined_detection(APP_PACKAGE)

        if success:
            logger.info(" 组合检测流程完成!")
        else:
            logger.info(" 组合检测流程部分失败，请查看日志")

    except Exception as e:
        logger.error(f"  程序初始化失败: {str(e)}")

import time
import random
import uiautomator2 as u2
import json
import os
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = [
    "我", "设置", "隐私", "个性化", "推荐", "广告", "私密", "消息", "权限", "内容",
    "仅我自己", "管理", "直播", "电商", "找到我的方式", "服务", "更多"
]


def log_action(file_handle, step, action_type, activity, element_info=None):
    log_entry = {
        "timestamp": time.time(),
        "step": step,
        "action_type": action_type,
        "activity": activity,
        "element_text": None,
        "element_id": None,
        "element_desc": None,
        "element_class": None
    }

    if element_info:
        log_entry["element_text"] = element_info.get('text', '')
        log_entry["element_id"] = element_info.get('resourceId', '')
        log_entry["element_desc"] = element_info.get('contentDescription', '')
        log_entry["element_class"] = element_info.get('className', '')

    file_handle.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    file_handle.flush()


try:
    d = u2.connect(os.getenv("DEVICE_SERIAL"))
except Exception as e:
    exit(1)

TOTAL_DURATION_SECONDS = float(os.getenv("TEST_DURATION", 403.2))
TARGET_PACKAGE = os.getenv("TARGET_PACKAGE")
random.seed(42)

d.app_start(TARGET_PACKAGE)
time.sleep(3)

start_time = time.time()
last_page_source_hash = ""
stuck_counter = 0
step_counter = 0

path_log_file = open("path_log_baseline2.jsonl", "w", encoding="utf-8")

try:
    while (time.time() - start_time) < TOTAL_DURATION_SECONDS:
        step_counter += 1
        current_app = d.app_current()
        current_activity = current_app.get('activity', 'UnknownActivity')

        if current_app.get('package') != TARGET_PACKAGE:
            log_action(path_log_file, step_counter, "BACK_FROM_EXTERNAL", current_activity)
            d.press("back")
            time.sleep(1)
            if d.app_current().get('package') != TARGET_PACKAGE:
                d.app_start(TARGET_PACKAGE)
            continue

        current_page_source = d.dump_hierarchy()
        current_hash = hash(current_page_source)

        if current_hash == last_page_source_hash:
            stuck_counter += 1
        else:
            stuck_counter = 0

        last_page_source_hash = current_hash

        if stuck_counter >= 3:
            log_action(path_log_file, step_counter, "BACK_FROM_STUCK", current_activity)
            d.press("back")
            stuck_counter = 0
            time.sleep(1)
            continue

        all_clickable_elements = d(clickable=True)
        matching_elements = []

        if all_clickable_elements.count > 0:
            for el in all_clickable_elements:
                el_info = el.info
                el_text = el_info.get('text', '') or ""
                el_desc = el_info.get('contentDescription', '') or ""
                el_combined_text = el_text + " " + el_desc

                if "退出" in el_combined_text or "登录" in el_combined_text or "注销" in el_combined_text:
                    continue

                for keyword in KEYWORDS:
                    if keyword in el_combined_text:
                        matching_elements.append(el)
                        break

        if matching_elements:
            element_to_click = random.choice(matching_elements)
            element_info = element_to_click.info
            log_action(path_log_file, step_counter, "CLICK", current_activity, element_info)
            element_to_click.click()
        else:
            log_action(path_log_file, step_counter, "SWIPE_DOWN", current_activity)
            d.swipe_ext("down", scale=0.6)

        time.sleep(0.5)

finally:
    if 'path_log_file' in locals() and not path_log_file.closed:
        path_log_file.close()
    d.app_stop(TARGET_PACKAGE)
import uiautomator2 as u2 
import time
import copy
import json
import os
from typing import List, Dict
from route import SimpleNavigator
from dotenv import load_dotenv
from screenshot_inspector import run_inspection

# 加载环境变量
load_dotenv()

privacy_switches: List[List[Dict]] = []
personality_switches: List[List[Dict]] = []
personality_layouts: List[List[Dict]] = []
enable_personalization_layout_dfs = True
def find_node_with_scroll(device: u2.Device, text: str, max_swipes: int = 10, swipe_delay: float = 0.5):
    for _ in range(max_swipes):
        node = device(text=text)
        if not node.exists:
            node = device(description=text)
        if node.exists:
            return node

        w, h = device.window_size()
        start_x, start_y = w // 2, int(h * 0.9)
        end_x,   end_y   = w // 2, int(h * 0.25)
        device.swipe(start_x, start_y, end_x, end_y, duration=0.3)
        time.sleep(swipe_delay)
    return None

def safe_click_by_hierarchy(device: u2.Device, cx: int, cy: int,
                            max_retries: int = 2, wait_time: float = 1.0) -> bool:
    prev_xml = device.dump_hierarchy()
    for attempt in range(1, max_retries + 1):
        device.click(cx, cy)
        time.sleep(wait_time)
        new_xml = device.dump_hierarchy()
        if new_xml != prev_xml:
            return True
    return False

def dfs_explore(device: u2.Device, curr_path: List[Dict]):
    result = run_inspection(device)
    time.sleep(0.5)

    if not result:
        return False, False

    is_current_page_popup = result.get("isPopup")

    if not is_current_page_popup:
        w, h = device.window_size()
        for _ in range(5):
            device.swipe(w//2, int(h*0.3), w//2, int(h*0.8), 0.5)
            time.sleep(0.8)
    for sw in result.get("switches", []):
        curr_path.append({
            "text": sw["text"],
            "current_state": sw["current_state"],
            "recommended_state": sw["recommended_state"],
            "analysis": sw["analysis"]
        })
        privacy_switches.append(copy.deepcopy(curr_path))
        curr_path.pop()

    personalization = result.get("personalization", {})

    for psw in personalization.get("switches", []):
        curr_path.append({
            "text": psw["text"],
            "current_state": psw["current_state"],
            "recommended_state": psw["recommended_state"],
            "analysis": psw["analysis"]
        })
        personality_switches.append(copy.deepcopy(curr_path))
        curr_path.pop()

    for layout in result.get("layouts", []):
        text = layout["text"]
        node = find_node_with_scroll(device, text)
        if not node:
            w, h = device.window_size()
            device.swipe(w // 2, int(h * 0.8), w // 2, int(h * 0.1), duration=0.3)
            time.sleep(0.5)
            continue

        info = node.info.get("bounds", {})
        left, top = info["left"], info["top"]
        right, bottom = info["right"], info["bottom"]
        cx = (left + right) // 2
        cy = (top + bottom) // 2

        curr_path.append({"text": text})
        if not safe_click_by_hierarchy(device, cx, cy):
            curr_path.pop()
            continue

        time.sleep(1)

        sub_explore_success, is_popup_after_sub_explore = dfs_explore(device, curr_path)

        if is_popup_after_sub_explore:
            old_page_hierarchy = device.dump_hierarchy()
            w, h = device.window_size()
            device.click(w / 2, h / 9)
            time.sleep(2)
            new_page_hierarchy = device.dump_hierarchy()
            if old_page_hierarchy == new_page_hierarchy:
                device.press("back")
            time.sleep(1)
        else:
            device.press("back")
            time.sleep(1)

        if not sub_explore_success:
            curr_path.pop()
            return False, False

        curr_path.pop()


    for playout in personalization.get("layouts", []):
        text = playout["text"]
        node = find_node_with_scroll(device, text)
        if not node:
            continue

        curr_path.append({"text": text})
        personality_layouts.append(copy.deepcopy(curr_path))

        if enable_personalization_layout_dfs:
            info = node.info.get("bounds", {})
            left, top = info["left"], info["top"]
            right, bottom = info["right"], info["bottom"]
            cx = (left + right) // 2
            cy = (top + bottom) // 2

            success = safe_click_by_hierarchy(device, cx, cy)
            if success:
                dfs_explore(device, curr_path)
                device.press("back")
                time.sleep(0.5)

        curr_path.pop()
    return True, is_current_page_popup

def main():
    device = u2.connect(os.getenv("DEVICE_SERIAL"))
    device.settings["wait_timeout"] = 20.0

    curr_path: List[Dict] = []
    APP_PACKAGE = device.app_current()['package']
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    navigator = SimpleNavigator(
        device_serial=os.getenv("DEVICE_SERIAL"),
        app_package=APP_PACKAGE,
        gemini_api_key=GEMINI_API_KEY
    )
    prefix = navigator.navigate()
    for node in prefix:
        curr_path.append({"text": node["text"], "bounds": node["bounds"]})

    success, _ = dfs_explore(device, curr_path)
    if not success:
        exit(1)

    if not privacy_switches and not personality_switches and not personality_layouts:
        return

    output_dir = "all_paths_results"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_pkg = APP_PACKAGE.replace(".", "_")
    output_file = os.path.join(output_dir, f"{safe_pkg}_{timestamp}.json")

    final_output = {
        "privacy_switches": [
            {
                **({"bounds": node.get("bounds")} if "bounds" in node else {}),
                **({"text": node["text"]} if "text" in node else {}),
                **({"current_state": node["current_state"],
                    "recommended_state": node["recommended_state"],
                    "analysis": node["analysis"]}
                   if "recommended_state" in node else {})
            }
            for path in privacy_switches
            for node in path
        ],
        "personality": {
            "personality_switches": [
                {
                    **({"bounds": node.get("bounds")} if "bounds" in node else {}),
                    **({"text": node["text"]} if "text" in node else {}),
                    **({"current_state": node["current_state"],
                        "recommended_state": node["recommended_state"],
                        "analysis": node["analysis"]}
                       if "recommended_state" in node else {})
                }
                for path in personality_switches
                for node in path
            ],
            "personality_layouts": [
                {"text": node["text"], **({"bounds": node.get("bounds")} if "bounds" in node else {})}
                for path in personality_layouts
                for node in path
            ]
        }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

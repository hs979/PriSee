import json
import os


def convert_log_to_config(input_path, output_path):
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return

    config_data = {
        "steps": [],
        "switch": []
    }

    processed_texts = set()
    all_items = []

    if 'personality' in log_data and 'personality_layouts' in log_data['personality']:
        all_items.extend(log_data['personality']['personality_layouts'])

    if 'personality' in log_data and 'personality_switches' in log_data['personality']:
        for item in log_data['personality']['personality_switches']:
            all_items.append(item)

    if 'privacy_switches' in log_data:
        all_items.extend(log_data['privacy_switches'])

    for item in all_items:
        text = item.get('text', '')
        bounds = item.get('bounds', None)
        item_id = f"{text}_{bounds}"
        
        if item_id in processed_texts:
            continue
        processed_texts.add(item_id)

        if bounds:
            step_entry = {
                "bounds": bounds,
                "turnback": "false"
            }
            config_data["steps"].append(step_entry)
        else:
            if text:
                switch_entry = {
                    "text": text,
                    "turnback": "false"
                }
                config_data["switch"].append(switch_entry)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)
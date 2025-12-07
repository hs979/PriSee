from openai import OpenAI
import base64
from PIL import Image
from io import BytesIO
import json

def analyze_privacy_switches(image_path: str, api_key: str, prompt_path: str, system_path: str) -> dict:
    def encode_compressed_image(image_path, quality=40, max_size=9 * 1024 * 1024):
        with Image.open(image_path) as img:
            img = img.convert("RGB")  # JPEG 不支持透明通道
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=quality)
            img_data = buffered.getvalue()
            while len(img_data) > max_size and quality > 10:
                quality -= 5
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=quality)
                img_data = buffered.getvalue()
            return base64.b64encode(img_data).decode("utf-8")

    # 读取提示词文件
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_text = f.read()

    with open(system_path, "r", encoding="utf-8") as f:
        system_text = f.read()

    base64_image = encode_compressed_image(image_path)

    reasoning_content = ""
    answer_content = ""
    is_answering = False

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    completion = client.chat.completions.create(
        model="qvq-max-latest",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                    },
                    {"type": "text", "text": prompt_text},
                ],
            },
        ],
        stream=True,
        seed=1234,
        temperature=0,
    )

    for chunk in completion:
        if not chunk.choices:
            pass
        else:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content != None:
                reasoning_content += delta.reasoning_content
            else:
                if delta.content != "" and is_answering is False:
                    is_answering = True
                answer_content += delta.content

    cleaned_text = answer_content.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json"):].strip()
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-len("```")].strip()

    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        return {}

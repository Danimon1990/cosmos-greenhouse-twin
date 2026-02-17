from flask import Flask, request, jsonify
from transformers import AutoProcessor, AutoModelForImageTextToText
import torch, base64, io
from PIL import Image

print("Loading model...")
model_name = "nvidia/Cosmos-Reason2-2B"
processor = AutoProcessor.from_pretrained(model_name)
model = AutoModelForImageTextToText.from_pretrained(
    model_name, torch_dtype=torch.bfloat16, device_map="auto"
)
print("Model loaded!")

app = Flask(__name__)

@app.route("/v1/chat/completions", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 1024)
    images = []
    text_parts = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    text_parts.append(part["text"])
                elif part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        b64 = url.split(",", 1)[1]
                        img = Image.open(io.BytesIO(base64.b64decode(b64)))
                        images.append(img)
    chat_messages = [{"role": "user", "content": []}]
    for img in images:
        chat_messages[0]["content"].append({"type": "image", "image": img})
    chat_messages[0]["content"].append({"type": "text", "text": "\n".join(text_parts)})
    prompt = processor.apply_chat_template(chat_messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[prompt], images=images if images else None, return_tensors="pt", padding=True)
    inputs = {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}
    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=max_tokens)
    input_len = inputs["input_ids"].shape[1]
    result = processor.decode(output_ids[0][input_len:], skip_special_tokens=True)
    return jsonify({
        "choices": [{"message": {"role": "assistant", "content": result}, "index": 0}],
        "model": model_name,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

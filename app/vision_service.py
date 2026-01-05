import base64
import json
from openai import OpenAI
from .config import OPENAI_API_KEY
from .recommendation_service import get_stress_recommendations

client = OpenAI(api_key=OPENAI_API_KEY)

VISION_PROMPT = """
You are a mental health emotion detection assistant.

Analyze the facial expression and infer emotional stress.

Return JSON only:
{
  "stress_level": "low | medium | high",
  "emotional_state": "1–2 sentence description",
  "confidence": 0.0-1.0
}
"""

async def analyze_image_with_gpt4_vision(image_bytes: bytes, user_id: str):
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]
            }
        ],
        max_tokens=300,
        temperature=0.2
    )

    # Extract and parse the JSON response
    content = response.choices[0].message.content
    content = content.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Fallback if GPT output is malformed
        result = {"stress_level": "unknown", "emotional_state": content, "confidence": 0.0}

    # Add recommendations if stressed
    if result.get("stress_level") in ["medium", "high"]:
        context = result.get("emotional_state", "")
        result["recommendations"] = await get_stress_recommendations(user_id, context)
    else:
        result["recommendations"] = []

    return result

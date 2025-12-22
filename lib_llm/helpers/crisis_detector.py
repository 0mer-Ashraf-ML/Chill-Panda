import json
from openai import AsyncOpenAI
from typing import Optional

class CrisisDetector:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def detect_crisis(self, text: str) -> bool:
        """
        Detects if the given text contains signs of crisis (self-harm/suicide).
        Returns True if crisis is detected, False otherwise.
        """
        if not text or len(text.strip()) < 3:
            return False

        system_prompt = (
            "You are a specialized crisis detection assistant. "
            "Analyze the following user input for any signs of self-harm, suicide ideation, or serious emotional crisis. "
            "If the user is expressing a desire to hurt themselves, end their life, or is in immediate danger of doing so, respond with 'true'. "
            "Otherwise, respond with 'false'. "
            "Respond ONLY with 'true' or 'false'."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0,
                max_tokens=5,
            )
            
            result = response.choices[0].message.content.strip().lower()
            return "true" in result
        except Exception as e:
            print(f"[CrisisDetector] Error: {e}")
            return False

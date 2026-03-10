# app/prompt_generator.py
from .llm_prompts import BASE_SYSTEM_PROMPT, ROLE_PROMPTS, DEFAULT_ROLE


def generate_system_prompt(role: str | None = None, language: str = "en") -> str:
    """
    Generates the final system prompt by combining:
    - Base Chill Panda system prompt
    - Role-specific behavior prompt
    - Language instruction

    Args:
        role (str): User-selected role (best_friend, parent, coach)
        language (str): Language code (en, zh-HK, zh-TW)

    Returns:
        str: Full system prompt for the LLM
    """

    selected_role = role if role in ROLE_PROMPTS else DEFAULT_ROLE
    role_prompt = ROLE_PROMPTS[selected_role]

    if language == "zh-HK":
        lang_instruction = "\n\nCRITICAL: Respond ONLY in Cantonese (Traditional Chinese, Hong Kong style)."
    elif language == "zh-TW":
        lang_instruction = "\n\nCRITICAL: Respond ONLY in Mandarin (Traditional Chinese, Taiwan style)."
    else:
        lang_instruction = "\n\nCRITICAL: Respond ONLY in English."

    return f"""
{BASE_SYSTEM_PROMPT}

------------------------------
{role_prompt}
------------------------------

Always follow BOTH the base Chill Panda identity
and the selected role behavior above.
{lang_instruction}
"""

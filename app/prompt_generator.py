# app/prompt_generator.py
from .llm_prompts import BASE_SYSTEM_PROMPT, ROLE_PROMPTS, DEFAULT_ROLE


def generate_system_prompt(role: str | None = None) -> str:
    """
    Generates the final system prompt by combining:
    - Base Chill Panda system prompt
    - Role-specific behavior prompt

    Args:
        role (str): User-selected role (best_friend, parent, coach)

    Returns:
        str: Full system prompt for the LLM
    """

    selected_role = role if role in ROLE_PROMPTS else DEFAULT_ROLE
    role_prompt = ROLE_PROMPTS[selected_role]

    return f"""
{BASE_SYSTEM_PROMPT}

------------------------------
{role_prompt}
------------------------------

Always follow BOTH the base Chill Panda identity
and the selected role behavior above.
"""

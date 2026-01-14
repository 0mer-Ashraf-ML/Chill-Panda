from api_request_schemas import (LanguageEnum, RoleEnum)
from lib_llm.helpers.prompts import generic
from lib_llm.helpers.prompts import roles

class PromptGenerator:
    def __init__(self, language: LanguageEnum = LanguageEnum.english, role: RoleEnum | None = None):
        self.language = language
        self.role = role
        
        # Start with generic prompt
        base_prompt = generic.prompt.strip()
        
        # Add role overlay if selected
        role_overlay = ""
        if role:
            if role == RoleEnum.loyal_best_friend:
                role_overlay = roles.loyal_best_friend
            elif role == RoleEnum.caring_parent:
                role_overlay = roles.caring_parent
            elif role == RoleEnum.coach:
                role_overlay = roles.coach
            elif role == RoleEnum.funny_friend:
                role_overlay = roles.funny_friend
        
        # Add language instruction
        lang_instruction = f"\n\nCRITICAL: Respond ONLY in {language.value} language."
        if language == LanguageEnum.english:
            lang_instruction = "\n\nCRITICAL: Respond ONLY in English."
        elif language == LanguageEnum.french:
            lang_instruction = "\n\nCRITICAL: Respond ONLY in French."
        elif language == LanguageEnum.zh_hk:
            lang_instruction = "\n\nCRITICAL: Respond ONLY in Cantonese (Traditional Chinese, Hong Kong style)."
        elif language == LanguageEnum.zh_tw:
            lang_instruction = "\n\nCRITICAL: Respond ONLY in Mandarin (Traditional Chinese, Taiwan style)."

        self.prompt = ( base_prompt + "\n" + role_overlay + "\n" + lang_instruction).strip()
        
        print(f"[{'Generic' if not role else role.value}] System Prompt loaded for language: {language.value}")
        self.serialize_prompt()

    def serialize_prompt(self):
        return self.prompt.strip()
    
    def append_conversation_context(self, summary: str) -> None:
        """
        Append conversation history summary to the prompt.
        
        Args:
            summary: Formatted summary of previous messages
        """
        if summary:
            self.prompt += f"\n\n## Previous Conversation Context\n{summary}"
            print(f"📜 Appended conversation context to prompt ({len(summary)} chars)")

    def __repr__(self):
        return self.prompt
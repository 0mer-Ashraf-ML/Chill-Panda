from api_request_schemas import (LanguageEnum)
from lib_llm.helpers.prompts import generic

class PromptGenerator:
    def __init__(self, language: LanguageEnum = LanguageEnum.english):
        self.language = language
        # Use generic prompt for all languages
        self.raw_prompt = generic
        self.prompt = self.raw_prompt.prompt.strip()
        print(f"<< Generic System Prompt loaded >>")
        self.serialize_prompt()

    def serialize_prompt(self):
        return self.prompt.strip()

    def __repr__(self):
        return self.prompt
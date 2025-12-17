from pydantic import BaseModel
from enum import Enum

class invoke_llm_schema(BaseModel):
    guid : str
    user_msg : str


class SourceEnum(str, Enum):
    device = "device"
    phone = "phone"

class LanguageEnum(str, Enum):
    french = "french"
    english = "english"
    spanish = "spanish"
    chinese = "chinese"
    japanese = "japanese"
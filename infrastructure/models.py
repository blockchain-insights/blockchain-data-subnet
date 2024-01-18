from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, validator

class HotkeyType(Enum):
    MINER = "miner"
    VALIDATOR = "validator"

class Hotkey(BaseModel):
    hotkey: str
    hotkeyMetadata: Optional[str]
    hotkeyType: str
    @validator('hotkeyType', pre=True)
    def convert_type_to_string(cls, v):
        if isinstance(v, HotkeyType):
            return v.value
        return v

class User(BaseModel):
    userName: str
    email: EmailStr
    password: str  # This should be hashed and never stored in plain text
    hotkeys: List[Hotkey] = []
    jwtRefreshTokens: Optional[List[str]] = []
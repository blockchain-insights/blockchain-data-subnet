from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr

class HotkeyType(Enum):
    MINER = "miner"
    VALIDATOR = "validator"

class Hotkey(BaseModel):
    hotkey: str
    hotkeyMetadata: Optional[str]
    hotkeyType: HotkeyType

class User(BaseModel):
    userName: str
    email: EmailStr
    password: str  # This should be hashed and never stored in plain text
    hotkeys: List[Hotkey] = []
    jwtRefreshTokens: Optional[List[str]] = []
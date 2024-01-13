from pydantic import BaseModel, EmailStr
from typing import List, Optional

class Miner(BaseModel):
    minerHotkey: str
    minerMetadata: str

class Validator(BaseModel):
    validatorHotkey: str
    validatorMetadata: str

class User(BaseModel):
    userName: str
    email: EmailStr
    password: str  # This should be hashed and never stored in plain text
    miners: List[Miner] = []
    validators: List[Validator] = []
    jwtRefreshTokens: Optional[List[str]] = []

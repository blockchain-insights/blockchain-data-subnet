from pydantic import BaseModel
from typing import List, Optional

class User(BaseModel):
    userName: str
    email: str
    password: str
    minerHotkeys: Optional[List[str]] = []
    validatorHotkeys: Optional[List[str]] = []
    jwtRefreshTokens: Optional[List[str]] = []

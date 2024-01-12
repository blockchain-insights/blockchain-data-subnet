from fastapi import APIRouter, HTTPException
from models import User
from database import get_user_collection
from security import get_password_hash

router = APIRouter()

@router.post("/register")
async def register_user(user: User):
    user_collection = get_user_collection()
    user.password = get_password_hash(user.password)
    # Insert user in DB and send email
    # ...
    return {"message": "User registered successfully"}
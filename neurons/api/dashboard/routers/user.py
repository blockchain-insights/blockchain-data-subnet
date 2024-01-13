from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from neurons.api.dashboard.models import User
from neurons.api.dashboard.database import get_user_collection
from neurons.api.dashboard.security import get_password_hash
import smtplib
from email.message import EmailMessage
from typing import Optional
from pydantic import EmailStr
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

router = APIRouter()

class UserRegistrationModel(User):
    email: Optional[EmailStr] = None

def send_email(recipient_email: str, username: str, password: str):
    msg = EmailMessage()
    msg.set_content(f"Hello {username},\n\nYour account has been created.\nUsername: {username}\nPassword: {password}")

    msg['Subject'] = 'Your Account Details'
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = recipient_email

    # Send the message via SMTP server
    with smtplib.SMTP(os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT")) as server:
        server.starttls()
        server.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
        server.send_message(msg)

@router.post("/register", response_model=UserRegistrationModel)
async def register_user(user: UserRegistrationModel):
    user_collection = get_user_collection()
    if user_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict.update({"password": hashed_password})
    user_collection.insert_one(user_dict)

    # Send email
    send_email(user.email, user.username, user.password)

    return user

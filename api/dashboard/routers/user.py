from fastapi import APIRouter, HTTPException
from api.dashboard.models import User
from api.dashboard.database import get_user_collection
from api.dashboard.security import get_password_hash
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from typing import Optional
from pydantic import EmailStr
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

router = APIRouter()

class UserRegistrationModel(User):
    email: Optional[EmailStr] = None


def send_email(recipient_email: str, username: str, password: str):
    message = Mail(
        from_email=os.getenv("EMAIL_SENDER"),
        to_emails=recipient_email,
        subject='Your Account Details',
        plain_text_content=f'Hello {username},\n\nYour account has been created.\nUsername: {username}\nPassword: {password}'
    )

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)
        print(response.status_code, response.body, response.headers)
    except Exception as e:
        print(e)

@router.post("/register", response_model=UserRegistrationModel)
async def register_user(user: UserRegistrationModel):
    user_collection = get_user_collection()

    # Check for duplicate username
    if user_collection.find_one({"userName": user.userName}):
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check for duplicate email
    if user.email and user_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    user_dict = user.dict(exclude_unset=True)
    user_dict.update({"password": hashed_password})
    user_collection.insert_one(user_dict)

    # Send email if email is provided
    if user.email:
       send_email(user.email, user.userName, user.password)

    return user


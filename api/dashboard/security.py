from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

# OAuth2 token retrieval scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    """
    Hash a password.

    Args:
    password (str): The plain text password.

    Returns:
    str: The hashed password.
    """
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    """
    Verify a plain password against the hashed version.

    Args:
    plain_password (str): The plain text password.
    hashed_password (str): The hashed password.

    Returns:
    bool: True if the password matches, False otherwise.
    """
    print(plain_password)
    print(hashed_password)
    return pwd_context.verify(plain_password, hashed_password)

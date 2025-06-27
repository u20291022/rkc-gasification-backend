from fastapi import APIRouter
from pydantic import BaseModel
import hashlib
from app.models.models import User

router = APIRouter()


class UserAuth(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    authenticated: bool


def get_md5_hash(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()


@router.post("/login", response_model=AuthResponse)
async def authenticate_user(user_data: UserAuth):
    user = await User.filter(email=user_data.email).first()
    if not user:
        return AuthResponse(authenticated=False)
    hashed_password = get_md5_hash(user_data.password)
    if hashed_password != user.password_hash:
        return AuthResponse(authenticated=False)
    return AuthResponse(
        authenticated=True,
    )

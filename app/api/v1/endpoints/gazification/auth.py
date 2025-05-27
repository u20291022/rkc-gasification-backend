from fastapi import APIRouter
from pydantic import BaseModel
import hashlib
from app.models.models import User

router = APIRouter()

# Схема данных для аутентификации
class UserAuth(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    authenticated: bool

# Функция для создания MD5 хеша пароля
def get_md5_hash(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

# Эндпоинт для аутентификации пользователя
@router.post("/login", response_model=AuthResponse)
async def authenticate_user(user_data: UserAuth):
    # Ищем пользователя по email
    user = await User.filter(email=user_data.email).first()
    
    # Если пользователь не найден
    if not user:
        return AuthResponse(authenticated=False)
    
    # Проверяем пароль
    hashed_password = get_md5_hash(user_data.password)
    if hashed_password != user.password_hash:
        return AuthResponse(authenticated=False)
    
    # Успешная аутентификация
    return AuthResponse(
        authenticated=True,
    )


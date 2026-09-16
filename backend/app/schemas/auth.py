from pydantic import BaseModel, EmailStr

from app.models.enums import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    full_name: str
    user_id: int


class CurrentUser(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}

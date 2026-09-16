from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Role


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}

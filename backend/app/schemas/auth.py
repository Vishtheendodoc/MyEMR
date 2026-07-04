from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=150)
    qualifications: str | None = None
    kmc_number: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str | None
    display_name: str | None
    role: str
    qualifications: str | None
    kmc_number: str | None
    doctor_name: str

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=150)
    qualifications: str | None = None
    kmc_number: str | None = None

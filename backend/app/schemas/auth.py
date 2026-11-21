from pydantic import BaseModel, EmailStr, Field, field_validator


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
    clinic_id: int = 1
    acting_doctor_id: int | None = None
    acting_clinic_id: int | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=150)
    qualifications: str | None = None
    kmc_number: str | None = None


DESK_ROLES = {"registration", "billing", "pharmacy"}


class ActingDoctorRequest(BaseModel):
    doctor_id: int


class StaffCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    display_name: str = Field(min_length=1, max_length=150)
    role: str

    @field_validator("role")
    @classmethod
    def desk_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in DESK_ROLES and role != "nurse":
            raise ValueError("Choose registration, billing, pharmacy, or nurse")
        return role


class StaffPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=100)
    is_active: bool | None = None

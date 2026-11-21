from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    new_refresh_jti,
    verify_password,
)
from app.models import ClinicProfile, RefreshSession, User
from app.schemas.auth import (
    DESK_ROLES,
    ActingDoctorRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    StaffCreateRequest,
    StaffPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services.audit import write_audit
from app.services.rate_limit import allow_login

router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _next_clinic_id(db: Session) -> int:
    user_max = db.query(func.max(User.clinic_id)).scalar() or 0
    profile_max = db.query(func.max(ClinicProfile.clinic_id)).scalar() or 0
    return max(int(user_max), int(profile_max)) + 1


def _optional_user(request: Request, db: Session) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    payload = decode_token(header[7:].strip())
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        return None
    user = db.get(User, int(payload["sub"]))
    return user if user and getattr(user, "is_active", True) is not False else None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    # A doctor account can see every chart in its clinic, so nobody anonymous may create one
    # unless this is the very first doctor or public registration was switched on.
    doctor_exists = db.query(User).filter(User.role == "doctor").first() is not None
    caller = _optional_user(request, db)
    if doctor_exists and not settings.allow_public_registration and not (caller and caller.role in ("doctor", "admin")):
        raise HTTPException(status_code=403, detail="Sign in as a doctor to add another doctor account")
    email = normalize_email(data.email)
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    name = data.display_name.strip()
    clinic_id = _next_clinic_id(db)
    user = User(
        username=email,
        email=email,
        display_name=name,
        password=hash_password(data.password),
        role="doctor",
        qualifications=data.qualifications,
        kmc_number=data.kmc_number,
        clinic_id=clinic_id,
    )
    try:
        db.add(user)
        db.add(ClinicProfile(
            clinic_id=clinic_id,
            name=name,
            signatory=name,
            reminder_doctor_name=name,
        ))
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    from app.api.v1.clinic_admin import _seed_prices

    _seed_prices(db, clinic_id)
    return user


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    jti = new_refresh_jti()
    expires = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshSession(jti=jti, user_id=user.id, expires_at=expires))
    db.commit()
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id), jti),
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not allow_login(f"{client_ip}|{(data.email or '').strip().lower()}"):
        raise HTTPException(status_code=429, detail="Too many login attempts. Wait a minute and try again.")
    email = normalize_email(data.email)
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh" or not payload.get("jti"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    session = db.query(RefreshSession).filter_by(jti=payload["jti"]).first()
    if not session or session.revoked_at is not None or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.get(User, int(payload["sub"]))
    if not user or user.id != session.user_id or getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=401, detail="User not found")
    session.revoked_at = datetime.utcnow()
    replacement = new_refresh_jti()
    session.replaced_by = replacement
    expires = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshSession(jti=replacement, user_id=user.id, expires_at=expires))
    db.commit()
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id), replacement),
    )


@router.post("/logout")
def logout(data: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if payload and payload.get("jti"):
        session = db.query(RefreshSession).filter_by(jti=payload["jti"]).first()
        if session and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
            db.commit()
    return {"success": True}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.display_name = data.display_name.strip()
    if user.role == "doctor":
        user.qualifications = data.qualifications
        user.kmc_number = data.kmc_number
    db.commit()
    db.refresh(user)
    return user


def _active_doctors(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "doctor", or_(User.is_active.is_(None), User.is_active.is_(True)))
        .order_by(User.display_name, User.id)
        .all()
    )


@router.get("/doctors", response_model=list[UserResponse])
def list_doctors(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in DESK_ROLES and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only desk staff can choose a doctor")
    return _active_doctors(db)


@router.patch("/acting-doctor", response_model=UserResponse)
def set_acting_doctor(
    data: ActingDoctorRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in DESK_ROLES:
        raise HTTPException(status_code=403, detail="Only pharmacy, billing, and registration can switch doctors")
    doctor = db.get(User, data.doctor_id)
    if not doctor or doctor.role != "doctor" or doctor.is_active is False:
        raise HTTPException(status_code=404, detail="Doctor not found")
    user.acting_doctor_id = doctor.id
    user.acting_clinic_id = doctor.clinic_id
    db.commit()
    db.refresh(user)
    return user


def _require_doctor(user: User) -> int:
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only a doctor can add desk logins")
    return user.clinic_id or 1


@router.get("/staff", response_model=list[UserResponse])
def list_staff(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clinic_id = _require_doctor(user)
    return (
        db.query(User)
        .filter(User.clinic_id == clinic_id, User.role.in_(list(DESK_ROLES) + ["nurse"]))
        .order_by(User.role, User.display_name)
        .all()
    )


@router.post("/staff", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    data: StaffCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinic_id = _require_doctor(user)
    email = normalize_email(data.email)
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    staff = User(
        username=email,
        email=email,
        display_name=data.display_name.strip(),
        password=hash_password(data.password),
        role=data.role,
        clinic_id=clinic_id,
    )
    try:
        db.add(staff)
        db.commit()
        db.refresh(staff)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    return staff


@router.patch("/staff/{staff_id}", response_model=UserResponse)
def update_staff(
    staff_id: int,
    data: StaffPasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinic_id = _require_doctor(user)
    staff = db.get(User, staff_id)
    if not staff or staff.clinic_id != clinic_id or staff.role not in (set(DESK_ROLES) | {"nurse"}):
        raise HTTPException(status_code=404, detail="Desk account not found")
    if data.password:
        staff.password = hash_password(data.password)
        write_audit(
            db,
            user_id=user.id,
            action="staff.password_reset",
            entity_type="user",
            entity_id=staff.id,
            details=staff.email,
        )
    if data.is_active is not None:
        staff.is_active = data.is_active
        write_audit(
            db,
            user_id=user.id,
            action="staff.deactivate" if not data.is_active else "staff.activate",
            entity_type="user",
            entity_id=staff.id,
            details=staff.email,
        )
    if not data.password and data.is_active is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    db.commit()
    db.refresh(staff)
    return staff

# pyright: reportMissingImports=false, reportMissingModuleSource=false
import os
import random
import re
import smtplib
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import (
    AuthResponse,
    EmailRequest,
    UserCreate,
    UserLogin,
    UserRead,
    VerifyOTPRequest,
)
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

OTP_STORAGE: dict[str, dict[str, Any]] = {}
OTP_STORAGE_LOCK = Lock()
OTP_TTL_MINUTES = 5
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(value))


def create_otp() -> str:
    return str(random.randint(1000, 9999)).zfill(4)


def store_otp(email: str, otp: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
    with OTP_STORAGE_LOCK:
        OTP_STORAGE[email] = {"otp": otp, "expires_at": expires_at}


def verify_otp(email: str, otp: str) -> None:
    with OTP_STORAGE_LOCK:
        stored = OTP_STORAGE.get(email)

    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has not been sent for this email",
        )

    if stored["otp"] != otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    expires_at = stored["expires_at"]
    if datetime.now(timezone.utc) > expires_at:
        with OTP_STORAGE_LOCK:
            OTP_STORAGE.pop(email, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired",
        )

    with OTP_STORAGE_LOCK:
        OTP_STORAGE.pop(email, None)


def send_email_with_otp(email: str, otp: str) -> None:
    smtp_host = os.getenv("SMTP_HOST") or os.getenv("EMAIL_HOST")
    smtp_username = os.getenv("SMTP_USERNAME") or os.getenv("EMAIL_HOST_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_HOST_PASSWORD")
    if not smtp_host or not smtp_username or not smtp_password:
        raise RuntimeError(
            "Email delivery is not configured. Set SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD.",
        )

    smtp_port = int(os.getenv("SMTP_PORT", os.getenv("EMAIL_PORT", "587")))
    sender_email = (
        os.getenv("SMTP_FROM_EMAIL")
        or os.getenv("EMAIL_FROM")
        or smtp_username
        or "noreply@example.com"
    )

    message = EmailMessage()
    message["Subject"] = "Cresco verification code"
    message["From"] = sender_email
    message["To"] = email
    message.set_content(
        f"Your Cresco verification code is {otp}. It is valid for {OTP_TTL_MINUTES} minutes.",
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(message)


@router.post("/send-otp")
def send_otp(payload: EmailRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    email = normalize_email(payload.email)
    if not is_valid_email(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please enter a valid email id",
        )

    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    otp = create_otp()
    try:
        send_email_with_otp(email, otp)
    except (OSError, RuntimeError, smtplib.SMTPException) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to send OTP email: {error}",
        ) from error

    store_otp(email, otp)
    return {"message": "OTP sent successfully", "email": email}


@router.post("/verify-otp")
def verify_otp_route(payload: VerifyOTPRequest) -> dict[str, str]:
    email = normalize_email(payload.email)
    if not is_valid_email(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please enter a valid email id",
        )

    verify_otp(email, payload.otp)
    return {"message": "OTP verified successfully"}


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> AuthResponse:
    username = payload.username.strip().lower()
    email = normalize_email(payload.email)

    if not is_valid_email(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please enter a valid email id",
        )

    verify_otp(email, payload.otp)

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered",
        ) from None

    wallet = Wallet(
        user_id=user.id,
        balance=Decimal("100000.00"),
    )
    db.add(wallet)
    db.commit()
    db.refresh(user)

    return AuthResponse(
        access_token=create_access_token(user.id),
        user=user,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> AuthResponse:
    identifier = payload.username_or_email.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(
                User.username == identifier,
                User.email == identifier,
            ),
        ),
    )

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
        )

    return AuthResponse(
        access_token=create_access_token(user.id),
        user=user,
    )


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

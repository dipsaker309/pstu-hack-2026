import pytest
from fastapi import HTTPException

from app.routes.auth import create_otp, is_valid_email, store_otp, verify_otp


def test_email_validation_accepts_valid_email():
    assert is_valid_email("user@example.com") is True
    assert is_valid_email("USER+tag@sub.example.org") is True


def test_email_validation_rejects_invalid_email():
    assert is_valid_email("invalid-email") is False
    assert is_valid_email("missing-domain@") is False


def test_otp_generation_uses_four_digits():
    otp = create_otp()

    assert len(otp) == 4
    assert otp.isdigit()


def test_verify_otp_rejects_invalid_codes():
    store_otp("demo@example.com", "1234")

    verify_otp("demo@example.com", "1234")

    store_otp("demo@example.com", "1234")
    with pytest.raises(HTTPException, match="Invalid OTP"):
        verify_otp("demo@example.com", "0000")

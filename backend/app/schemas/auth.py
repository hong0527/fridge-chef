"""인증 스키마 (NFR-SEC-002)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=64)
    allergies: list[str] = Field(default_factory=list, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    allergies: list[str]
    is_email_verified: bool = False


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1)


class UpdateProfileRequest(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=64)
    current_password: str | None = None
    new_password: str | None = Field(None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdateProfileRequest:
        if self.nickname is None and self.new_password is None:
            raise ValueError("nickname 또는 new_password 중 하나 이상을 입력해주세요.")
        return self


class UpdateAllergiesRequest(BaseModel):
    allergies: list[str] = Field(default_factory=list, max_length=50)

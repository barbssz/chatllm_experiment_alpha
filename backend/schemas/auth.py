from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        # A aplicacao trata todo o endereco como insensivel a maiusculas.
        return value.strip().lower() if isinstance(value, str) else value


class RegisterRequest(LoginRequest):
    password: SecretStr = Field(min_length=15, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str

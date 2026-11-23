"""Credentials accepted by the Swagger password-login helper."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class PasswordLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254, examples=["tester@example.com"])
    password: SecretStr = Field(min_length=1, max_length=4096)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip()
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("Enter a valid email address.")
        local, domain = value.split("@")
        if not local or not domain:
            raise ValueError("Enter a valid email address.")
        return value


class AccessTokenRead(BaseModel):
    access_token: str = Field(min_length=1, repr=False)
    token_type: Literal["bearer"]
    expires_in: int = Field(gt=0, strict=True)

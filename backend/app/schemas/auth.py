# Auth API schemas: validate the Google credential request and serialize success messages.
from pydantic import BaseModel


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    message: str

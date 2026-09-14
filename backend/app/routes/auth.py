# HTTP layer: extract request data and cookies → call AuthService → return profile or auth response.
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import AuthResponse, GoogleLoginRequest
from app.services.auth import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/google",
    response_model=AuthResponse,
)
async def google_login(
    payload: GoogleLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a Google credential for authentication cookies.

    Delegate login to AuthService and translate ValueError into a sanitized
    HTTP 401. Return the service success message through AuthResponse.
    """
    try:
        return await AuthService.login_with_google(
            db=db,
            response=response,
            credential=payload.credential,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        ) from exc


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return public profile fields for the user resolved by the auth dependency.

    Authentication failures are handled before this route body executes.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
    }


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Pass the refresh cookie to AuthService to rotate the session.

    No request body or valid access cookie is required. The service sets
    replacement cookies or raises HTTP 401 for invalid refresh credentials.
    """
    return await AuthService.refresh_tokens(db, response, refresh_token)


@router.post("/logout", response_model=AuthResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Delegate session revocation and cookie clearing to AuthService.

    Missing refresh cookies are allowed so repeated logout remains successful.
    """
    return await AuthService.logout(db, response, refresh_token)

# Auth workflow: verify identity → use repositories → commit session changes → set or clear cookies.
import uuid

from fastapi import HTTPException, Response, status
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils.tokens import (
    generate_refresh_token,
    get_refresh_token_expiry,
    hash_refresh_token,
)
from app.models.user import User
from app.repositories.refresh_session import RefreshSessionRepository
from app.repositories.tokens import create_access_token, decode_access_token
from app.repositories.user import UserRepository


class AuthService:
    @staticmethod
    async def login_with_google(
        db: AsyncSession,
        response: Response,
        credential: str,
    ) -> dict:
        # Verify Google token
        """Verify a Google ID token, find/create its user, and establish a session.

        Use db for repository operations and response for HttpOnly cookies.
        Persist a refresh-token hash, commit it, then set both cookies and return
        a success message. UserRepository.create currently commits new users
        separately. Invalid Google credentials raise ValueError; the route
        converts that error to HTTP 401.
        """
        try:
            google_user = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                settings.google_client_id,
            )
        except ValueError as exc:
            raise ValueError("Invalid Google token") from exc

        # Get Google user details
        google_id = google_user["sub"]
        email = google_user["email"]

        # Find existing user
        user = await UserRepository.get_by_google_id(
            db=db,
            google_id=google_id,
        )

        # Create user if this is their first login
        if user is None:
            user = await UserRepository.create(
                db=db,
                google_id=google_id,
                email=email,
                name=google_user.get("name"),
                avatar_url=google_user.get("picture"),
            )

        # Create access token
        access_token = create_access_token(user.id)

        # Create refresh token
        refresh_token = generate_refresh_token()

        # Store only the refresh token hash
        await RefreshSessionRepository.create(
            db=db,
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=get_refresh_token_expiry(),
        )
        await db.commit()
        AuthService.set_auth_cookies(response, access_token, refresh_token)

        return {"message": "login Successfull"}

    @staticmethod
    def set_auth_cookies(
        response: Response, access_token: str, refresh_token: str
    ) -> None:
        """Attach access and refresh tokens to response as HttpOnly cookies.

        Use configured security flags and lifetimes. The access cookie applies
        to /; the refresh cookie is restricted to /auth. No database writes occur.
        """
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            max_age=settings.access_token_expire_minutes * 60,
            path="/",
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/auth",
        )

    @staticmethod
    async def get_current_user(
        db: AsyncSession,
        access_token: str,
    ) -> User:
        # decode the access token and get the id from the sub field
        # find user by that id
        # return the current user.
        """Validate an access JWT and return the User identified by its subject.

        Read through db without committing. Raise ValueError when token
        validation fails, the subject is invalid, or the user no longer exists.
        """
        try:
            payload = decode_access_token(access_token)
            user_id = uuid.UUID(payload["sub"])

        except (ValueError, KeyError):
            raise ValueError("Invalid access token")

        user = await UserRepository.get_by_id(
            db=db,
            user_id=user_id,
        )

        if user is None:
            raise ValueError("User not found")

        return user

    @staticmethod
    def get_me(user: User) -> dict:
        """Build a public profile dictionary from an already authenticated User.

        This helper performs no authentication or database work. The current
        /me route builds the same response directly.
        """
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
        }

    @staticmethod
    async def refresh_tokens(
        db: AsyncSession,
        response: Response,
        refresh_token: str | None,
    ) -> dict:
        """Rotate a valid refresh cookie and return a success message.

        Conditionally revoke the matching unexpired session so only one request
        can consume it. Stage the replacement hash and commit both changes in
        one transaction. Roll back on failure and set response cookies only
        after commit. Missing, invalid, expired, or revoked tokens raise HTTP 401.
        """
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing refresh token",
            )

        try:
            session = await RefreshSessionRepository.revoke(
                db, hash_refresh_token(refresh_token), active_only=True
            )
            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token",
                )
            user = await UserRepository.get_by_id(db, session.user_id)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                )

            access_token = create_access_token(user.id)
            new_refresh_token = generate_refresh_token()
            # Stage the replacement before committing the entire rotation.
            await RefreshSessionRepository.create(
                db=db,
                user_id=user.id,
                token_hash=hash_refresh_token(new_refresh_token),
                expires_at=get_refresh_token_expiry(),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        AuthService.set_auth_cookies(response, access_token, new_refresh_token)
        return {"message": "Token refreshed successfully"}

    @staticmethod
    async def logout(
        db: AsyncSession,
        response: Response,
        refresh_token: str | None,
    ) -> dict:
        """Revoke the supplied refresh session and clear both response cookies.

        Commit revocation before clearing cookies; roll back database failures.
        Missing or already-revoked sessions still succeed. Other sessions are
        unaffected, and previously issued access JWTs remain valid until expiry.
        """
        if refresh_token:
            try:
                await RefreshSessionRepository.revoke(
                    db, hash_refresh_token(refresh_token)
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        for key, path in (("access_token", "/"), ("refresh_token", "/auth")):
            response.delete_cookie(
                key=key,
                path=path,
                httponly=True,
                secure=settings.cookie_secure,
                samesite=settings.cookie_samesite,
            )
        return {"message": "Logged out successfully"}

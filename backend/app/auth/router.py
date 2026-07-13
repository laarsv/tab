"""Google-OAuth-Login (wie die anderen Tools): Redirect → Callback → Session-Cookie."""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from ..config import settings
from .cookies import clear_session_cookie, set_session_cookie
from .deps import get_current_user
from .google import oauth
from .session import encode_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.OAUTH_REDIRECT_URI)


@router.get("/callback")
async def callback(request: Request):
    frontend = settings.FRONTEND_URL.rstrip("/") or ""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(f"{frontend}/login?{urlencode({'error': 'oauth_failed'})}")

    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)
    email = (userinfo.get("email") or "").lower()
    name = userinfo.get("name") or email
    picture = userinfo.get("picture")

    if not email or email not in settings.allowed_emails_list:
        return RedirectResponse(f"{frontend}/login?{urlencode({'error': 'not_allowed'})}")

    response = RedirectResponse(settings.FRONTEND_URL or "/")
    set_session_cookie(response, encode_session(email, name=name, picture=picture))
    return response


@router.post("/logout", status_code=204)
async def logout():
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user

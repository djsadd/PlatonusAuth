import os
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth import auth

app = FastAPI()

KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")


def _require_keycloak_config() -> None:
    missing = [
        name
        for name, value in (
            ("KEYCLOAK_BASE_URL", KEYCLOAK_BASE_URL),
            ("KEYCLOAK_REALM", KEYCLOAK_REALM),
            ("KEYCLOAK_CLIENT_ID", KEYCLOAK_CLIENT_ID),
        )
        if not value
    ]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing Keycloak configuration: {', '.join(missing)}",
        )


def _keycloak_openid_base() -> str:
    return (
        f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"
        "/protocol/openid-connect"
    )

class Login(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(data: Login):
    try:
        result = auth(data.username, data.password)
        return {
            "success": True,
            "role": result["role"],
            "info": result["info"]
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/authorize")
def authorize(
    redirect_uri: str = Query(...),
    response_type: str = Query("code"),
    scope: str = Query("openid"),
    state: Optional[str] = Query(None),
):
    _require_keycloak_config()

    params = {
        "client_id": KEYCLOAK_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "scope": scope,
    }
    if state:
        params["state"] = state

    authorize_url = httpx.URL(f"{_keycloak_openid_base()}/auth", params=params)
    return RedirectResponse(str(authorize_url), status_code=307)


@app.post("/token")
def token(
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    scope: Optional[str] = Form(None),
):
    _require_keycloak_config()

    payload = {
        "grant_type": grant_type,
        "client_id": KEYCLOAK_CLIENT_ID,
    }
    if KEYCLOAK_CLIENT_SECRET:
        payload["client_secret"] = KEYCLOAK_CLIENT_SECRET

    optional_fields = {
        "code": code,
        "redirect_uri": redirect_uri,
        "refresh_token": refresh_token,
        "username": username,
        "password": password,
        "scope": scope,
    }
    payload.update({key: value for key, value in optional_fields.items() if value is not None})

    try:
        response = httpx.post(
            f"{_keycloak_openid_base()}/token",
            data=payload,
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Keycloak token request failed: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text}

    if response.is_error:
        raise HTTPException(status_code=response.status_code, detail=body)

    return body


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=9000)

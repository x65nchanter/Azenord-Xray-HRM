import base64
import io
import os
import secrets
from pathlib import Path

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.models import User

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"

router = APIRouter(prefix="/v1/sub")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@router.get("/{user_uuid}/papers")
async def get_resident_papers(
    request: Request,
    user_uuid: str,
    pls: str = Query(..., description="One-time secret token"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    # 1. Find user by UUID
    user = session.exec(select(User).where(User.uuid == user_uuid)).first()

    if not user:
        raise HTTPException(status_code=404, detail="Resident not found")

    # 2. Validate the One-Time Token (pls)
    if user.papers_token != pls:
        # Security: If token is wrong, we don't even tell them why
        raise HTTPException(status_code=403, detail="Access Denied: Invalid or expired link")

    # 3. ROTATE TOKEN (Burn after reading)
    # Generate a fresh 64-char hex token for the NEXT visit
    new_token = secrets.token_hex(64)
    user.papers_token = new_token
    session.add(user)
    session.commit()
    session.refresh(user)

    sub_url = f"https://{settings.API_DOMAIN}/v1/sub/{user.uuid}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(sub_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#00ff41", back_color="#0a0a0a")
    buf = io.BytesIO()
    img.save(buf)
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    return templates.TemplateResponse(
        "papers.html",
        {
            "request": request,
            "status": "Active" if user.is_active else "Banned",
            "nickname": user.nickname,
            "email": user.email,
            "internal_ip": user.internal_ip,
            "dns_name": user.dns_name,
            "is_active": user.is_active,
            "qr_code": qr_base64,
            "next_link": sub_url,
        },
    )

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.models import User

router = APIRouter(prefix="/v1/sub")


@router.get("/{user_uuid}/papers")
async def get_resident_papers(
    user_uuid: str,
    pls: str = Query(..., description="One-time secret token"),
    session: Session = Depends(get_session),
):
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

    status = "Verified"
    if user.is_active:
        status = "Verified"
    else:
        status = "Blocked"

    # 4. Prepare data for the Page (HTML response or JSON)
    return {
        "status": status,
        "nickname": user.nickname,
        "email": user.email,
        "internal_ip": user.internal_ip,
        "dns_name": user.dns_name,
        "is_active": user.is_active,
    }

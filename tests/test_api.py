import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

from app.api.main import app


@pytest.mark.asyncio
async def test_api_health(session: Session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/sub/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "Azenord: Invalid subscription"

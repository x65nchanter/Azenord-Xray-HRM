import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

from app.api.main import app
from app.core.models import Route, RoutePolicy, User


@pytest.mark.asyncio
async def test_api_routing_logic(session: Session):
    """Verify that API correctly separates proxy and direct routes in JSON"""
    # 1. Seed the data
    test_uuid = "12345678-1234-5678-1234-567812345678"
    user = User(nickname="neo", email="neo@yourdomain.com", uuid=test_uuid, internal_ip="10.0.8.2")

    # Proxy routes
    r1 = Route(pattern="domain:google.com", policy=RoutePolicy.proxy)
    # Direct routes
    r2 = Route(pattern="domain:local-service.home", policy=RoutePolicy.direct)

    session.add_all([user, r1, r2])
    session.commit()

    # 2. Use httpx ASGITransport instead of TestClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/v1/sub/{test_uuid}")

    # 3. Assertions
    assert response.status_code == 200
    data = response.json()
    rules = data["routing"]["rules"]

    # Check Direct
    direct_rule = next(r for r in rules if r["outboundTag"] == "direct")
    assert "domain:local-service.home" in direct_rule["domain"]

    # Check Proxy
    proxy_rule = next(r for r in rules if r["outboundTag"] == "proxy")
    assert "domain:google.com" in proxy_rule["domain"]


@pytest.mark.asyncio
async def test_empty_routing_table(session: Session):
    """Verify API handles empty routes gracefully"""
    u = User(nickname="empty", email="e@a.pro", uuid="empty-uuid", internal_ip="10.0.8.99")
    session.add(u)
    session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/sub/empty-uuid")

    assert response.status_code == 200
    assert "routing" in response.json()

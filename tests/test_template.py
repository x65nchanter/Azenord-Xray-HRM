import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

from app.api.main import app
from app.core.config import settings
from app.core.constants import InboundTag
from app.core.models import Route, RoutePolicy, User


@pytest.mark.asyncio
async def test_config_template_integrity(session: Session):
    """Проверка целостности структуры конфига и корректности маппинга данных"""

    # 1. Готовим данные (Seed)
    test_uuid = "aabbccdd-1122-3344-5566-77889900aabb"
    user = User(
        nickname="master", email="admin@yourdomain.com", uuid=test_uuid, internal_ip="10.0.8.2"
    )

    # Добавляем маршрут, чтобы проверить фабрику роутинга
    route = Route(pattern="domain:google.com", policy=RoutePolicy.proxy)

    session.add_all([user, route])
    session.commit()

    # 2. Делаем запрос к API (используя новый транспорт)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/v1/sub/{test_uuid}")

    assert response.status_code == 200
    config = response.json()

    # --- ПРОВЕРКА 1: DNS & FakeDNS ---
    assert "fakedns" in config
    assert config["dns"]["hosts"]["master.azenord"] == "10.0.8.2"
    assert "https://1.1.1.1" in config["dns"]["servers"]

    # --- ПРОВЕРКА 2: Outbounds (Транспорты) ---
    outbounds = config["outbounds"]

    # Проверяем наличие нашего дефолтного транспорта из .env
    vision_tag = InboundTag.VISION.value  # "vless-vision"
    vision_outbound = next((o for o in outbounds if o["tag"] == vision_tag), None)

    assert vision_outbound is not None, f"Транспорт {vision_tag} не найден в конфиге"
    assert vision_outbound["protocol"] == "vless"
    assert vision_outbound["settings"]["vnext"][0]["users"][0]["id"] == test_uuid
    assert vision_outbound["streamSettings"]["tlsSettings"]["serverName"] == settings.SERVER_ADDR

    # --- ПРОВЕРКА 3: Routing (Правила) ---
    rules = config["routing"]["rules"]

    # Проверяем системное правило Mesh (оно должно быть в начале или существовать)
    mesh_rule = next((r for r in rules if r.get("domain") == ["domain:.azenord"]), None)
    assert mesh_rule is not None
    assert mesh_rule["outboundTag"] == settings.DEFAULT_MESH_OUTBOUND.value

    # Проверяем правило из БД
    db_rule = next((r for r in rules if r.get("domain") == ["domain:google.com"]), None)
    assert db_rule is not None
    # В нашем API прокси-правила из БД ведут на 'proxy' (или твой RoutePolicy.proxy.value)
    assert db_rule["outboundTag"] == RoutePolicy.proxy.value

    #  --- ПРОВЕРКА 4: Безопасность и Целостность ---
    assert config["email"] == "admin@yourdomain.com"

    # Считаем, сколько раз UUID встречается в конфиге.
    # Должно быть ровно по одному разу на каждый активный inbound
    expected_count = len(settings.inbound_tags_list)
    actual_count = str(config).count(test_uuid)

    assert actual_count == expected_count, (
        f"UUID ожидался {expected_count} раз (по числу транспортов), "
        f"но найден {actual_count} раз. Проверь утечки данных!"
    )


@pytest.mark.asyncio
async def test_api_security_leak(session: Session):
    """Ensure that private data (like other users' UUIDs) is NOT leaked in the config"""
    u1 = User(nickname="u1", email="e1", uuid="secret-uuid-1", internal_ip="10.0.8.2")
    u2 = User(nickname="u2", email="e2", uuid="secret-uuid-2", internal_ip="10.0.8.3")
    session.add_all([u1, u2])
    session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/sub/secret-uuid-1")

    config_str = response.text
    # Should contain the current user's UUID but NOT the other user's UUID
    assert "secret-uuid-1" in config_str
    assert "secret-uuid-2" not in config_str

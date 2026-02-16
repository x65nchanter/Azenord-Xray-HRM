from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, select

from app.api.main import app
from app.cli.commands.user import add_user
from app.core.config import settings
from app.core.constants import InboundTag
from app.core.models import Route, RoutePolicy, User


@pytest.mark.asyncio
async def test_api_invalid_uuid_format(session: Session):
    """Edge Case: What if the UUID is just gibberish?"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Testing a non-UUID string
        response = await ac.get("/v1/sub/not-a-uuid-at-all")

    # It should still return 404, not 500
    assert response.status_code == 404
    assert response.json()["detail"] == "Azenord: Invalid subscription"


def test_cli_duplicate_nickname(session: Session):
    """Edge Case: Adding a user with a nickname that already exists"""
    # 1. Add initial user
    u1 = User(nickname="Neo", email="neo@matrix.com", uuid="uuid1", internal_ip="10.0.8.2")
    session.add(u1)
    session.commit()

    # 2. Try to add another Neo via CLI logic
    with patch("app.cli.commands.user.xray") as mocked_xray:
        mocked_xray.check_connection.return_value = True

        from app.cli.commands.user import add_user

        add_user("Neo", "other@matrix.com")  # This should trigger the 'exists' check

        # 3. Verify only ONE Neo exists in DB
        users = session.exec(select(User).where(User.nickname == "Neo")).all()
        assert len(users) == 1


def test_ipam_out_of_bounds(session: Session):
    """Edge Case: What happens if the database has a manual IP outside the range?"""
    # Manually inject a weird IP
    u1 = User(nickname="hacker", email="h@a.pro", uuid="u1", internal_ip="192.168.1.1")
    session.add(u1)
    session.commit()

    # IPAM should ignore it and still start from 10.0.8.2
    from app.utils.ipam import get_next_free_ip

    next_ip = get_next_free_ip(session)
    assert next_ip == "10.0.8.2"


@pytest.mark.asyncio
async def test_api_banned_user_access(session: Session):
    """Edge Case: Does a banned user (is_active=False) get a config?"""
    u = User(
        nickname="Smith", email="s@a.pro", uuid="banned-id", internal_ip="10.0.8.5", is_active=False
    )
    session.add(u)
    session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/sub/banned-id")

    # Banned users should be treated as non-existent for the subscription API
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_subscription_leak_protection(session: Session):
    """Edge Case: Нельзя получить чужую подписку, даже если знаешь структуру URL"""
    u1 = User(nickname="neo", email="n@a.pro", uuid="uuid-1", internal_ip="10.0.8.2")
    u2 = User(nickname="trinity", email="t@a.pro", uuid="uuid-2", internal_ip="10.0.8.3")
    session.add_all([u1, u2])
    session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Запрашиваем конфиг Нео
        response = await ac.get("/v1/sub/uuid-1")

    # В конфиге Нео НЕ должно быть упоминания UUID Тринити
    assert "uuid-2" not in response.text
    # Но никнейм Тринити должен быть в DNS hosts (так как это Mesh)
    assert "trinity.azenord" in response.json()["dns"]["hosts"]


def test_ipam_full_subnet_collision(session: Session):
    """Edge Case: Что если мы заполнили абсолютно все доступные IP?"""
    from app.utils.ipam import get_next_free_ip

    # 1. Эмулируем полную сеть: забиваем все IP от .2 до .254
    # Это гарантирует, что цикл в get_next_free_ip не найдет свободных мест
    for i in range(2, 255):
        full_user = User(
            nickname=f"user_{i}", email=f"u{i}@a.pro", uuid=f"uuid-{i}", internal_ip=f"10.0.8.{i}"
        )
        session.add(full_user)

    session.commit()

    # 2. Теперь попытка получить следующий IP ОБЯЗАНА вызвать ValueError
    with pytest.raises(ValueError, match="Mesh subnet is full"):
        get_next_free_ip(session)


def test_config_invalid_inbound_tag_in_env(session: Session):
    """Edge Case: Что если в .env прописан несуществующий тег?"""
    from app.utils.xray_config_factory import OutboundFactory

    # Пытаемся создать outbound для тега, которого нет в Enum
    config = OutboundFactory.create_outbound("vless-ultra-turbo", "some-uuid")

    # Фабрика должна вернуть пустой словарь, а не упасть с ошибкой
    assert config == {}


@pytest.mark.asyncio
async def test_api_route_priority_order(session: Session):
    """Edge Case: Проверка приоритета правил роутинга"""
    # Создаем правило в БД, которое конфликтует с системным Mesh-правилом
    conflict_route = Route(pattern="domain:.azenord", policy=RoutePolicy.direct)
    session.add(conflict_route)
    session.commit()

    u = User(nickname="test", email="t@a.pro", uuid="test-uuid", internal_ip="10.0.8.10")
    session.add(u)
    session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/sub/test-uuid")

    rules = response.json()["routing"]["rules"]

    # Первым правилом ДОЛЖНО идти системное правило .azenord -> proxy (Master Outbound)
    # Наша логика в API ставит системные правила в начало списка
    assert rules[0]["domain"] == ["domain:.azenord"]
    assert rules[0]["outboundTag"] == settings.DEFAULT_MESH_OUTBOUND.value


def test_cli_add_user_partial_grpc_failure(session):
    """Edge Case: Откат (Rollback) при частичном сбое gRPC (например, 2 из 3 Ок)"""

    with patch("app.cli.commands.user.xray") as mocked_xray:
        mocked_xray.check_connection.return_value = True
        # 1-й транспорт Ок, 2-й падает
        mocked_xray.add_user.side_effect = [True, False, True]

        # Запускаем через runner, чтобы проверить вывод
        from typer.testing import CliRunner

        from app.cli.main import app

        runner = CliRunner()

        result = runner.invoke(app, ["user", "add", "broken", "b@a.pro"])

        # Должен быть вызван remove_user для очистки того, что успели добавить
        assert mocked_xray.remove_user.called
        # В базе не должно быть юзера
        assert session.exec(select(User).where(User.nickname == "broken")).first() is None

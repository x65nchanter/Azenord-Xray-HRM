from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from app.cli.main import app
from app.core.models import User

runner = CliRunner()


@pytest.fixture
def mock_xray_user():
    """Фикстура для патчинга gRPC клиента в модуле user"""
    with patch("app.cli.commands.user.xray") as mocked:
        mocked.check_connection.return_value = True
        mocked.add_user.return_value = True
        mocked.remove_user.return_value = True
        yield mocked


def test_user_add_full_cycle(session, mock_xray_user):
    """Тест регистрации: БД + 3 транспорта gRPC"""
    nickname = "smith"
    email = "smith@matrix.com"

    # Запуск: python -m app.cli user add smith smith@matrix.com
    result = runner.invoke(app, ["user", "add", nickname, email])

    assert result.exit_code == 0
    assert "синхронизирован" in result.stdout

    # Проверка вызовов gRPC (по одному на каждый транспорт)
    assert mock_xray_user.add_user.call_count == 3

    # Проверка записи в БД
    user = session.query(User).filter_by(nickname=nickname).first()
    assert user is not None
    assert user.email == email
    assert user.internal_ip.startswith("10.0.8.")


def test_user_list_display(session):
    """Тест вывода таблицы пользователей"""
    # Добавляем тестового юзера напрямую в БД
    session.add(User(nickname="neo", email="neo@a.pro", uuid="id1", internal_ip="10.0.8.2"))
    session.commit()

    result = runner.invoke(app, ["user", "list"])

    assert result.exit_code == 0
    assert "neo" in result.stdout
    assert "10.0.8.2" in result.stdout


def test_user_info_with_stats(session, mock_xray_user):
    """Тест карточки пользователя с данными трафика"""
    user = User(nickname="trinity", email="t@a.pro", uuid="id2", internal_ip="10.0.8.3")
    session.add(user)
    session.commit()

    # Имитируем данные статистики от Xray
    mock_xray_user.get_traffic_stats.return_value = {
        "user>>>t@a.pro>>>traffic>>>downlink": 104857600  # 100 MB
    }

    result = runner.invoke(app, ["user", "info", "trinity"])

    assert result.exit_code == 0
    assert "100.00 MB" in result.stdout
    assert "10.0.8.3" in result.stdout


def test_user_ban_unban_logic(session, mock_xray_user):
    """Тест блокировки и разблокировки (is_active toggle)"""
    user = User(
        nickname="cypher", email="c@a.pro", uuid="id3", internal_ip="10.0.8.4", is_active=True
    )
    session.add(user)
    session.commit()

    # BAN
    runner.invoke(app, ["user", "ban", "cypher"])
    session.refresh(user)
    assert user.is_active is False
    assert mock_xray_user.remove_user.call_count == 3

    # UNBAN
    runner.invoke(app, ["user", "unban", "cypher"])
    session.refresh(user)
    assert user.is_active is True
    assert mock_xray_user.add_user.call_count == 3


def test_user_remove_complete(session, mock_xray_user):
    """Тест полного удаления из всех систем"""
    user = User(nickname="ghost", email="g@a.pro", uuid="id4", internal_ip="10.0.8.9")
    session.add(user)
    session.commit()

    result = runner.invoke(app, ["user", "remove", "ghost"])

    assert result.exit_code == 0
    assert mock_xray_user.remove_user.call_count == 3
    assert session.query(User).filter_by(nickname="ghost").first() is None

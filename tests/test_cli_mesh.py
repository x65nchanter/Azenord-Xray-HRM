import os
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from app.cli.main import app
from app.core.models import User

runner = CliRunner()


@pytest.fixture
def mock_xray_mesh():
    """Фикстура для патчинга gRPC в модуле mesh"""
    with patch("app.cli.commands.mesh.xray") as mocked:
        yield mocked


def test_mesh_status_online(session, mock_xray_mesh):  # Added session
    """Тест: Статус системы, когда Xray доступен"""
    mock_xray_mesh.check_connection.return_value = True

    # Убеждаемся, что база инициализирована (через фикстуру session)
    result = runner.invoke(app, ["mesh", "status"], color=False)

    assert result.exit_code == 0
    assert "ONLINE" in result.stdout
    assert "Database: OK" in result.stdout


def test_mesh_status_offline(mock_xray_mesh):
    """Тест: Статус системы, когда gRPC упал"""
    mock_xray_mesh.check_connection.return_value = False

    result = runner.invoke(app, ["mesh", "status"])

    assert result.exit_code == 0  # Команда не должна падать, она просто рапортует
    assert "OFFLINE" in result.stdout


def test_mesh_stats_calculation(mock_xray_mesh):
    """Тест: Расчет суммарного трафика всей сети"""
    # Имитируем ответ от StatsService
    mock_xray_mesh.get_traffic_stats.return_value = {
        "user>>>neo@a.pro>>>traffic>>>downlink": 1073741824,  # 1 GB
        "user>>>trinity@a.pro>>>traffic>>>uplink": 536870912,  # 0.5 GB
        "inbound>>>api>>>traffic>>>downlink": 1024,  # Служебный трафик
    }

    result = runner.invoke(app, ["mesh", "stats"])

    # We strip ANSI codes manually for the check if Rich is being stubborn
    import re

    clean_stdout = re.compile(r"\x1b[^m]*m").sub("", result.stdout)

    assert result.exit_code == 0
    assert "1.00 GB" in clean_stdout
    assert "0.50 GB" in clean_stdout


def test_mesh_scan_logic(session):
    """Тест: Сканирование сети (имитация пинга)"""
    # Добавляем юзеров, которых будем "сканировать"
    session.add_all(
        [
            User(nickname="neo", email="n@a.pro", uuid="id1", internal_ip="10.0.8.2"),
            User(
                nickname="smith",
                email="s@a.pro",
                uuid="id2",
                internal_ip="10.0.8.3",
                is_active=False,
            ),
        ]
    )
    session.commit()

    # Патчим os.system, чтобы не запускать реальный пинг в системе
    with patch("os.system") as mocked_ping:
        # Имитируем, что нео доступен (0), а остальные нет
        mocked_ping.return_value = 0

        result = runner.invoke(app, ["mesh", "scan"])

        assert result.exit_code == 0
        assert "neo" in result.stdout
        # Проверяем, что сканируются только АКТИВНЫЕ юзеры
        assert "smith" not in result.stdout
        assert mocked_ping.called

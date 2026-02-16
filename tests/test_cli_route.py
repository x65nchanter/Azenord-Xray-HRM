import re

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from app.cli.main import app
from app.core.models import Route

runner = CliRunner()


def clean_ansi(text: str) -> str:
    return re.compile(r"\x1b[^m]*m").sub("", text)


def test_route_add_basic_proxy(session):
    """Test adding a simple proxy domain"""
    result = runner.invoke(
        app,
        ["route", "add", "--pattern=domain:google.com", "--policy=proxy"],
        catch_exceptions=False,
    )

    # Если всё еще exit 2, выводим stderr
    if result.exit_code != 0:
        print(f"ERROR STDERR: {result.stderr}")
        print(f"DEBUG STDOUT: {result.stdout}")

    assert result.exit_code == 0


def test_route_add_discord_voice_logic(session):
    """Test complex Discord UDP rule"""
    # Здесь паттерн не передаем вообще, только опции
    result = runner.invoke(
        app, ["route", "add", "--policy", "direct", "--network", "udp", "--port", "50000-65535"]
    )

    session.expire_all()
    assert result.exit_code == 0

    route = session.exec(select(Route).where(Route.port == "50000-65535")).first()
    assert route is not None


def test_route_lifecycle_with_id(session):
    """Full cycle: add -> see ID -> remove by ID"""
    # 1. Add (опять через явный флаг)
    add_res = runner.invoke(
        app, ["route", "add", "--pattern", "domain:test.com", "--policy", "proxy"]
    )
    assert add_res.exit_code == 0

    session.expire_all()

    # 2. List
    result_list = runner.invoke(app, ["route", "list"])
    assert "test.com" in clean_ansi(result_list.stdout)

    # 3. Remove
    # Выцепляем ID из базы, чтобы не гадать (в тестах это обычно 1)
    route_id = session.exec(select(Route.id)).first()
    remove_res = runner.invoke(app, ["route", "remove", str(route_id)])
    assert remove_res.exit_code == 0

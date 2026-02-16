import pytest
from typer.testing import CliRunner

from app.cli.__main__ import app
from app.core.config import settings
from app.core.models import User

runner = CliRunner()


@pytest.fixture
def test_resident(session):
    """Create a resident for sub tests"""
    user = User(
        nickname="neo", email="neo@yourdomain.com", uuid="my-secret-uuid-123", internal_ip="10.0.8.2"
    )
    session.add(user)
    session.commit()
    return user


def test_sub_link_output(session, test_resident):
    """Test: Does the link include the correct domain and UUID?"""
    # python -m app.cli sub link neo
    result = runner.invoke(app, ["sub", "link", "neo"])

    assert result.exit_code == 0
    # Check if our SERVER_ADDR from settings is in the output
    assert settings.SERVER_ADDR in result.stdout
    # Check if the correct UUID is there
    assert test_resident.uuid in result.stdout
    assert "✅ Подписка для neo готова" in result.stdout


def test_sub_link_user_not_found(session):
    """Test: Proper error when user doesn't exist"""
    result = runner.invoke(app, ["sub", "link", "nonexistent"])

    assert result.exit_code == 1
    assert "Ошибка: Пользователь 'nonexistent' не найден" in result.stdout


def test_sub_qr_generation(session, test_resident):
    """Test: Does the QR command execute and print ASCII blocks?"""
    # python -m app.cli sub qr neo
    result = runner.invoke(app, ["sub", "qr", "neo"])

    assert result.exit_code == 0
    # QR code in ASCII contains many spaces and block characters
    # We check for the header and the link inside the output
    assert f"QR-код для {test_resident.nickname}" in result.stdout
    assert test_resident.uuid in result.stdout


def test_sub_link_banned_warning(session, test_resident):
    """Test: Does the CLI warn us if we generate a link for a banned user?"""
    test_resident.is_active = False
    session.add(test_resident)
    session.commit()

    result = runner.invoke(app, ["sub", "link", "neo"])

    assert result.exit_code == 0
    assert "Внимание: Пользователь neo заблокирован" in result.stdout

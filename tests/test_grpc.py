import pytest

from app.core.grpc_client import AzenordXrayControl


@pytest.mark.integration  # Помечаем тест как интеграционный
@pytest.mark.asyncio
async def test_xray_grpc_connection():
    """Проверка связи с Xray gRPC (требует запущенного Xray)"""
    client = AzenordXrayControl(address="127.0.0.1:10085")
    is_alive = client.check_connection()

    assert is_alive is True, "Xray gRPC недоступен! Проверь порт 10085."

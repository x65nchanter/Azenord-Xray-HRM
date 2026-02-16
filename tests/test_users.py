from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app.cli.commands.user import add_user, list_users, remove_user, toggle_user
from app.core.models import User


@pytest.fixture
def temp_user(session: Session):
    user = User(
        nickname="Morpheus", email="morph@yourdomain.com", uuid="some-uuid", internal_ip="10.0.8.100"
    )
    session.add(user)
    session.commit()
    return user


# Тестируем добавление пользователя
def test_add_user_logic(session: Session):
    nickname = "Neo"
    email = "neo@yourdomain.com"

    # Патчим (подменяем) класс XrayControl, чтобы он не лез в сеть
    with patch("app.cli.commands.user.xray") as mocked_xray:
        # Имитируем успешные ответы gRPC
        mocked_xray.check_connection.return_value = True
        mocked_xray.add_user.return_value = True

        # Вызываем нашу команду (передаем аргументы вручную)
        add_user(nickname, email)

        # 1. Проверяем, что gRPC был вызван с правильными параметрами
        assert mocked_xray.add_user.call_count == 3

        # 2. Проверяем, что юзер появился в базе
        statement = select(User).where(User.nickname == nickname)
        db_user = session.exec(statement).first()

        assert db_user is not None
        assert db_user.email == email
        assert db_user.internal_ip.startswith("10.0.8.")


# Тестируем ситуацию, когда Xray OFFLINE
def test_add_user_xray_offline(session: Session):
    with patch("app.cli.commands.user.xray") as mocked_xray:
        mocked_xray.check_connection.return_value = False

        add_user("AgentSmith", "smith@matrix.com")

        # Проверяем, что в базу ничего не записалось
        statement = select(User).where(User.nickname == "AgentSmith")
        db_user = session.exec(statement).first()
        assert db_user is None


# 1. Тест удаления
def test_remove_user_logic(session: Session, temp_user: User):
    with patch("app.cli.commands.user.xray") as mocked_xray:
        mocked_xray.remove_user.return_value = True

        remove_user(temp_user.nickname)

        # Проверяем, что из базы пропал
        db_user = session.exec(select(User).where(User.nickname == temp_user.nickname)).first()
        assert db_user is None
        assert mocked_xray.remove_user.call_count == 3


# 2. Тест Бан / Разбан (Toggle)
def test_toggle_user_logic(session: Session, temp_user: User):
    with patch("app.cli.commands.user.xray") as mocked_xray:
        mocked_xray.remove_user.return_value = True
        mocked_xray.add_user.return_value = True

        # Сначала баним
        toggle_user(temp_user.nickname)
        session.refresh(temp_user)
        assert temp_user.is_active is False
        mocked_xray.remove_user.assert_called()

        # Теперь разбаниваем
        toggle_user(temp_user.nickname)
        session.refresh(temp_user)
        assert temp_user.is_active is True
        mocked_xray.add_user.assert_called()


# 3. Тест вывода списка (просто на отсутствие ошибок)
def test_list_users_no_error(session: Session, temp_user: User):
    # Тут мы просто проверяем, что функция не падает при наличии юзеров
    try:
        list_users()
    except Exception as e:
        pytest.fail(f"list_users() raised {e} unexpectedly!")


def test_add_user_rollback_on_failure(session: Session):
    with patch("app.cli.commands.user.xray") as mocked_xray:
        # Simulate: 1st tag OK, 2nd tag FAIL
        mocked_xray.check_connection.return_value = True
        mocked_xray.add_user.side_effect = [True, False, True]

        from app.cli.commands.user import add_user

        add_user("Glitch", "glitch@matrix.com")

        # 1. Verify remove_user was called for the 1st tag (the rollback)
        mocked_xray.remove_user.assert_called()

        # 2. Verify DB is empty
        db_user = session.exec(select(User).where(User.nickname == "Glitch")).first()
        assert db_user is None

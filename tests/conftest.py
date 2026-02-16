import pytest
from sqlmodel import Session, SQLModel

from app.core.database import engine, init_db


@pytest.fixture(name="session")
def session_fixture():
    # Создаем таблицы перед каждым тестом
    init_db()
    with Session(engine) as session:
        yield session
    # Чистим после себя (опционально)
    SQLModel.metadata.drop_all(engine)

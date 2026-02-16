from sqlmodel import Session, SQLModel, create_engine

from app.core.models import Route, RoutePolicy, User

from .config import settings

# Теперь база может лежать где угодно, согласно .env
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

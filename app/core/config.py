import os
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import InboundTag  # Импортируем наш Enum


class Settings(BaseSettings):
    # --- Сетевые настройки ---
    SERVER_ADDR: str
    XHTTP_PATH: str

    # --- Порты (берутся из .env) ---
    PORT_vless_vision: int = 4430
    PORT_vless_h2: int = 10002
    PORT_vless_h3: int = 4433

    # --- Управление Xray ---
    XRAY_GRPC_ADDR: str = "127.0.0.1:10085"

    # --- Инфраструктура ---
    DATABASE_URL: str = "sqlite:///./output/hrm_database.db"

    # --- Логика Mesh ---
    # Мы ожидаем строку через запятую: "vless-vision,vless-h2"
    ACTIVE_INBOUND_TAGS: str = "vless-vision,vless-h2,vless-h3"

    # Тег по умолчанию для роутинга .azenord
    DEFAULT_MESH_OUTBOUND: InboundTag = InboundTag.VISION
    CERT_PATH: str
    KEY_PATH: str
    # Имя юзера в системе
    SYSTEM_USER: str = "root"
    # Автоматически определяем корень проекта
    PROJECT_ROOT: str = os.getcwd()

    @property
    def inbound_tags_list(self) -> List[str]:
        """Превращает строку из .env в чистый список строк-тегов"""
        return [t.strip() for t in self.ACTIVE_INBOUND_TAGS.split(",") if t.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Позволяет добавлять свои комменты в .env
    )


settings = Settings()

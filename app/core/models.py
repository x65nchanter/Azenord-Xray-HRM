import secrets
import uuid
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel

from app.core.config import settings


class RoutePolicy(str, Enum):
    proxy = "proxy"
    direct = "direct"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nickname: str = Field(index=True, unique=True)
    email: str = Field(unique=True)
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True)
    internal_ip: str = Field(unique=True)
    is_active: bool = Field(default=True)
    dns_name: str = Field(unique=True)

    # Secure Link Logic
    papers_token: str = Field(default_factory=lambda: secrets.token_hex(64))

    def __init__(self, **data):
        if "dns_name" not in data and "nickname" in data:
            data["dns_name"] = f"{data['nickname']}.{settings.MESH_DOMAIN}"
        super().__init__(**data)

    @property
    def papers_link(self) -> str:
        # Dynamic link generation
        return f"https://{settings.API_DOMAIN}/v1/sub/{self.uuid}/papers?pls={self.papers_token}"


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pattern: Optional[str] = None  # geosite:discord, 1.1.1.1, etc.
    policy: RoutePolicy = Field(default=RoutePolicy.proxy)

    # Advanced fields
    network: Optional[str] = None  # "udp", "tcp", or "tcp,udp"
    port: Optional[str] = None  # "50000-65535"
    protocol: Optional[str] = None  # ["bittorrent"]

    # Client-specific (Attributes)
    process_name: Optional[str] = None  # for Windows (e.g., "Discord.exe")
    package_name: Optional[str] = None  # for Android (e.g., "com.discord")

    comment: Optional[str] = None

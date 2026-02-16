import uuid
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


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

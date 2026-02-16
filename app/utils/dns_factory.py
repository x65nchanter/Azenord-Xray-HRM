from typing import Any, Dict, List

from app.core.config import settings
from app.core.models import User


class DNSFactory:
    @staticmethod
    def build_hosts(users: List[User]) -> Dict[str, str]:
        """Creates the Mesh Phonebook: nickname.yourdomain.mesh -> 10.0.8.x"""
        return {f"{u.nickname}.{settings.MESH_DOMAIN}": u.internal_ip for u in users}

    @staticmethod
    def get_default_servers() -> List[Any]:
        return ["fakedns", "https://1.1.1.1", "8.8.8.8", "localhost"]

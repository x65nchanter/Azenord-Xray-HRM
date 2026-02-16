from typing import Any, Dict, List

from app.core.models import User


class DNSFactory:
    @staticmethod
    def build_hosts(users: List[User]) -> Dict[str, str]:
        """Creates the Mesh Phonebook: nickname.azenord -> 10.0.8.x"""
        return {f"{u.nickname}.azenord": u.internal_ip for u in users}

    @staticmethod
    def get_default_servers() -> List[Any]:
        return ["fakedns", "https://1.1.1.1", "8.8.8.8", "localhost"]

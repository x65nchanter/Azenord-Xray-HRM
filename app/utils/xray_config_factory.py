from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type

from app.core.config import settings
from app.core.constants import InboundTag


# --- Base Strategy (Абстрактная стратегия) ---
class OutboundStrategy(ABC):
    @abstractmethod
    def build(self, tag: str, user_uuid: str) -> Dict[str, Any]:
        pass

    def _get_base_user(self, user_uuid: str) -> Dict[str, Any]:
        return {"id": user_uuid, "encryption": "none"}


# --- Concrete Strategy: Vision (TCP + Vision) ---
class VisionStrategy(OutboundStrategy):
    def build(self, tag: str, user_uuid: str) -> Dict[str, Any]:
        user = self._get_base_user(user_uuid)
        user["flow"] = "xtls-rprx-vision"

        return {
            "tag": tag,
            "protocol": "vless",
            "settings": {
                "vnext": [
                    {
                        "address": settings.SERVER_ADDR,
                        "port": settings.PORT_vless_vision,
                        "users": [user],
                    }
                ]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {
                    "serverName": settings.SERVER_ADDR,
                    "alpn": ["http/1.1"],
                },
            },
        }


# --- Concrete Strategy: xHTTP (h2 / h3) ---
class XHttpStrategy(OutboundStrategy):
    def build(self, tag: str, user_uuid: str) -> Dict[str, Any]:
        is_h3 = "h3" in tag
        alpn = ["h3"] if is_h3 else ["h2"]
        port = settings.PORT_vless_h3 if is_h3 else settings.PORT_vless_h2

        return {
            "tag": tag,
            "protocol": "vless",
            "settings": {
                "vnext": [
                    {
                        "address": settings.SERVER_ADDR,
                        "port": port,
                        "users": [self._get_base_user(user_uuid)],
                    }
                ]
            },
            "streamSettings": {
                "network": "xhttp",
                "security": "tls",
                "tlsSettings": {"serverName": settings.SERVER_ADDR, "alpn": alpn},
                "xhttpSettings": {"path": settings.XHTTP_PATH, "mode": "stream-one"},
            },
        }


# --- Simple Factory (Фабрика стратегий) ---
class OutboundFactory:
    # Словарь стратегий теперь типизирован через Enum
    _strategies: Dict[InboundTag, Type[OutboundStrategy]] = {
        InboundTag.VISION: VisionStrategy,
        InboundTag.H2: XHttpStrategy,
        InboundTag.H3: XHttpStrategy,
    }

    @classmethod
    def create_outbound(cls, tag: str, user_uuid: str) -> Dict[str, Any]:
        try:
            # Пытаемся превратить строку из .env в Enum
            tag_enum = InboundTag(tag)
            strategy_class = cls._strategies.get(tag_enum)

            if strategy_class:
                return strategy_class().build(tag, user_uuid)
        except ValueError:
            # Если в .env пришла ахинея, которой нет в Enum
            return {}
        return {}

    @classmethod
    def get_standard_outbounds(cls) -> List[Dict[str, Any]]:
        return [
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ]

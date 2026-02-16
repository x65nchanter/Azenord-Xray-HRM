from enum import Enum


class InboundTag(str, Enum):
    VISION = "vless-vision"
    H2 = "vless-h2"
    H3 = "vless-h3"
    # Легко добавить новые:
    # GRPC = "vless-grpc"
    # SHADOWSOCKS = "ss-2022"

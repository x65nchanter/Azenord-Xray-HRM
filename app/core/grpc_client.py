from typing import Any, Optional, cast

import grpc

from app.core.config import settings
from app.core.xray_api.app.proxyman.command import command_pb2 as proxyman_command
from app.core.xray_api.app.proxyman.command import command_pb2_grpc as proxyman_service
from app.core.xray_api.app.stats.command import command_pb2 as stats_command
from app.core.xray_api.app.stats.command import command_pb2_grpc as stats_service
from app.core.xray_api.common.protocol import user_pb2
from app.core.xray_api.common.serial.typed_message_pb2 import TypedMessage
from app.core.xray_api.proxy.vless import account_pb2


class AzenordXrayControl:
    def __init__(self, address: Optional[str] = None):
        target = address or settings.XRAY_GRPC_ADDR
        self.channel = grpc.insecure_channel(target)
        self.handler_stub = proxyman_service.HandlerServiceStub(self.channel)
        self.stats_stub = stats_service.StatsServiceStub(self.channel)

    def check_connection(self) -> bool:
        try:
            # QueryStats с пустым паттерном — самый быстрый способ проверить API
            self.stats_stub.QueryStats(stats_command.QueryStatsRequest(pattern="", reset=False))
            return True
        except grpc.RpcError:
            return False

    def add_user(self, inbound_tag: str, email: str, user_uuid: str) -> bool:
        flow = "xtls-rprx-vision" if "vision" in inbound_tag.lower() else ""

        vless_acc = account_pb2.Account(id=user_uuid, flow=flow)

        user = user_pb2.User(
            email=email,
            level=0,
            account=TypedMessage(
                type="xray.proxy.vless.Account", value=vless_acc.SerializeToString()
            ),
        )

        op = proxyman_command.AddUserOperation(user=user)

        request = proxyman_command.AlterInboundRequest(
            tag=inbound_tag,
            operation=TypedMessage(
                type="xray.app.proxyman.command.AddUserOperation", value=op.SerializeToString()
            ),
        )

        try:
            self.handler_stub.AlterInbound(request)
            return True
        except Exception as e:
            print(f"DEBUG [AddUser]: {e}")
            return False

    def remove_user(self, inbound_tag: str, email: str) -> bool:
        """Удаляет пользователя из активного инбаунда Xray по Email"""
        op = proxyman_command.RemoveUserOperation(email=email)
        request = proxyman_command.AlterInboundRequest(
            tag=inbound_tag,
            operation=TypedMessage(
                type="xray.app.proxyman.command.RemoveUserOperation", value=op.SerializeToString()
            ),
        )
        try:
            self.handler_stub.AlterInbound(request)
            return True
        except Exception as e:
            print(f"DEBUG [RemoveUser]: {e}")
            return False

    def get_traffic_stats(self):
        """Получает реальные данные о трафике через StatsService"""
        try:
            response = self.stats_stub.QueryStats(
                stats_command.QueryStatsRequest(pattern="", reset=False)
            )
            return {stat.name: stat.value for stat in response.stat}
        except Exception as e:
            print(f"Stats Error: {e}")
            return {}

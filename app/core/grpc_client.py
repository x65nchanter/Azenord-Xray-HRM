import grpc
from google.protobuf import any_pb2

# ПРАВИЛЬНЫЕ ПУТИ (через полный путь проекта):
from app.core.xray_api.app.proxyman.command import command_pb2 as proxyman_command
from app.core.xray_api.app.proxyman.command import command_pb2_grpc as proxyman_service
from app.core.xray_api.app.stats.command import command_pb2 as stats_command
from app.core.xray_api.app.stats.command import command_pb2_grpc as stats_service
from app.core.xray_api.common.protocol import user_pb2
from app.core.xray_api.proxy.vless import account_pb2


class AzenordXrayControl:
    def __init__(self, address: str = "127.0.0.1:10085"):
        # Если адрес не передан, тянем из .env
        target = address or settings.XRAY_GRPC_ADDR
        self.channel = grpc.insecure_channel(target)
        self.handler_stub = proxyman_service.HandlerServiceStub(self.channel)
        self.stats_stub = stats_service.StatsServiceStub(self.channel)

    def check_connection(self) -> bool:
        """Проверка: жив ли gRPC интерфейс Xray"""
        try:
            # Пытаемся получить пустую статистику (просто пинг)
            self.stats_stub.GetStats(
                stats_command.GetStatsRequest(
                    name="inbound>>>api>>>traffic>>>downlink", reset=False
                )
            )
            return True
        except grpc.RpcError:
            return False

    def add_user(self, inbound_tag: str, email: str, user_uuid: str):
        vless_account = account_pb2.Account(id=user_uuid, flow="")
        user = user_pb2.User(email=email, level=0, account=self._pack(vless_account))

        op = proxyman_command.AddUserOperation(user=user)
        request = proxyman_command.AlterInboundRequest(tag=inbound_tag, operation=self._pack(op))

        try:
            self.handler_stub.AlterInbound(request)
            return True
        except Exception:
            return False

    def _pack(self, message):
        any_msg = any_pb2.Any()
        any_msg.Pack(message)
        return any_msg

    def remove_user(self, inbound_tag: str, email: str) -> bool:
        """Удаляет пользователя из активного инбаунда Xray по Email"""
        op = proxyman_command.RemoveUserOperation(email=email)
        request = proxyman_command.AlterInboundRequest(tag=inbound_tag, operation=self._pack(op))
        try:
            self.handler_stub.AlterInbound(request)
            return True
        except Exception:
            return False

    def get_traffic_stats(self):
        """Получает реальные данные о трафике через StatsService"""
        try:
            # Запрашиваем всю доступную статистику
            # pattern="" означает "дай всё, что есть"
            response = self.stats_stub.GetStats(
                stats_command.GetStatsRequest(pattern="", reset=False)
            )

            # Собираем в удобный словарик: { 'название': байты }
            return {stat.name: stat.value for stat in response.stat}
        except Exception as e:
            print(f"Stats Error: {e}")
            return {}

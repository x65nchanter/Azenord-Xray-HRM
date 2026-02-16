from app.core.grpc_client import AzenordXrayControl  # Наш gRPC класс

xray = AzenordXrayControl()  # Подключение к gRPC (127.0.0.1:10085)

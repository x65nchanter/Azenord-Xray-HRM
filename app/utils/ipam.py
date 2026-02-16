import ipaddress

from sqlmodel import Session, select

from app.core.models import User


def get_next_free_ip(session: Session, subnet: str = "10.0.8.0/24"):
    network = ipaddress.ip_network(subnet)
    # Пропускаем .0 (сеть) и .1 (шлюз)
    all_hosts = [str(ip) for ip in list(network.hosts())[1:]]

    # Получаем список уже занятых IP
    used_ips = session.exec(select(User.internal_ip)).all()

    for ip in all_hosts:
        if ip not in used_ips:
            return ip

    raise ValueError("Mesh subnet is full")

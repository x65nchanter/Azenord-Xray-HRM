import pytest
from sqlmodel import Session

from app.core.models import User
from app.utils.ipam import get_next_free_ip


def test_ipam_sequential_assignment(session: Session):
    """Checks if IPs are assigned one after another"""
    # 1. Add first user
    user1 = User(nickname="neo", email="n@a.pro", internal_ip="10.0.8.2", uuid="u1")
    session.add(user1)
    session.commit()

    # 2. Get next - should be .3
    next_ip = get_next_free_ip(session)
    assert next_ip == "10.0.8.3"


def test_ipam_fill_gaps(session: Session):
    """Checks if IPAM fills a hole in the middle (e.g., after user deletion)"""
    # 1. Manually create a gap: .2 and .4 are taken, .3 is free
    u2 = User(nickname="u2", email="u2@a.pro", internal_ip="10.0.8.2", uuid="uuid2")
    u4 = User(nickname="u4", email="u4@a.pro", internal_ip="10.0.8.4", uuid="uuid4")
    session.add(u2)
    session.add(u4)
    session.commit()

    # 2. The logic should find the smallest available IP
    next_ip = get_next_free_ip(session)
    assert next_ip == "10.0.8.3"


def test_ipam_subnet_overflow(session: Session):
    """Checks if it raises an error when the /24 subnet is full"""
    # To simulate overflow without adding 254 users, we can mock the used_ips list
    # or just add users in a loop for a true integration test
    for i in range(2, 255):
        u = User(nickname=f"u{i}", email=f"{i}@a.pro", internal_ip=f"10.0.8.{i}", uuid=f"id{i}")
        session.add(u)
    session.commit()

    with pytest.raises(ValueError) as excinfo:
        get_next_free_ip(session)

    assert "Mesh subnet is full" in str(excinfo.value)

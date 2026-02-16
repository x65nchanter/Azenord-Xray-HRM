import asyncio
import uuid

import pytest

from app.core.grpc_client import AzenordXrayControl

# Use the marker we defined earlier
pytestmark = pytest.mark.integration


@pytest.fixture
def xray_client():
    """Returns a real gRPC client connected to local Xray"""
    return AzenordXrayControl(address="127.0.0.1:10085")


@pytest.mark.asyncio
async def test_xray_user_lifecycle_integration(xray_client):
    """
    CRITICAL: Verifies that we can push a user to Xray memory
    and pull them out without errors.
    """
    test_email = f"test-{uuid.uuid4().hex[:6]}@yourdomain.com"
    test_uuid = str(uuid.uuid4())
    inbound_tag = "vless-main"

    # 1. ADD
    add_success = xray_client.add_user(inbound_tag, test_email, test_uuid)
    assert add_success is True, f"Failed to push user {test_email} to Xray"

    # Small delay for Xray to process memory
    await asyncio.sleep(0.5)

    # 2. REMOVE
    remove_success = xray_client.remove_user(inbound_tag, test_email)
    assert remove_success is True, f"Failed to remove user {test_email} from Xray"


@pytest.mark.asyncio
async def test_xray_stats_availability_integration(xray_client):
    """
    CRITICAL: Verifies that the Stats Service is active and
    returning the expected data structure.
    """
    stats = xray_client.get_traffic_stats()

    # We expect a dictionary (even if empty if no traffic yet)
    assert isinstance(stats, dict), "Stats Service returned invalid data type"

    # If Xray is configured correctly, we should see at least one 'traffic' metric
    if len(stats) > 0:
        first_stat_name = list(stats.keys())[0]
        assert ">>>" in first_stat_name, f"Unexpected stat format: {first_stat_name}"

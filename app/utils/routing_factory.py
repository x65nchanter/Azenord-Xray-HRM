from typing import Any, Dict, List

from app.core.config import settings
from app.core.models import Route


class RoutingFactory:
    @staticmethod
    def build_rules(db_routes: List[Route]) -> List[Dict[str, Any]]:
        """Transforms DB routes and System rules into Xray JSON rules"""

        # 1. System Rule: Mesh Network
        rules = [
            {
                "type": "field",
                "domain": ["domain:.azenord"],
                "outboundTag": settings.DEFAULT_MESH_OUTBOUND.value,
            }
        ]

        # 2. Transform DB Routes
        for r in db_routes:
            rule = {"type": "field", "outboundTag": r.policy.value}

            # Logic for Domain vs IP
            if r.pattern:
                if any(x in r.pattern for x in ["geosite", "domain", "keyword", "regexp"]):
                    rule["domain"] = str(r.pattern)
                else:
                    rule["ip"] = str(r.pattern)

            # Optional attributes
            if r.network:
                rule["network"] = r.network
            if r.port:
                rule["port"] = r.port
            if r.process_name:
                rule["process"] = str(r.process_name)
            if r.package_name:
                rule["packageName"] = str(r.package_name)

            rules.append(rule)

        return rules

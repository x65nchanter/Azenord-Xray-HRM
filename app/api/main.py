import base64
import json

import yaml
from fastapi import Depends, FastAPI, HTTPException, Response
from sqlmodel import Session, select

from app.api.routes import papers
from app.core.config import settings
from app.core.database import get_session
from app.core.models import Route, User
from app.utils.dns_factory import DNSFactory
from app.utils.routing_factory import RoutingFactory
from app.utils.xray_config_factory import OutboundFactory

app = FastAPI()
app.include_router(papers.router)


@app.get("/v1/sub/{user_uuid}")
async def get_subscription(user_uuid: str, session: Session = Depends(get_session)):
    # 1. Fetch Data
    user = session.exec(select(User).where(User.uuid == user_uuid, User.is_active)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Azenord: Invalid subscription")

    all_users = list(session.exec(select(User)).all())
    db_routes = list(session.exec(select(Route)).all())

    # 2. Build Components using Factories
    dns_hosts = DNSFactory.build_hosts(all_users)
    routing_rules = RoutingFactory.build_rules(db_routes)

    # 3. Build Outbounds (Transports)
    outbounds = [
        OutboundFactory.create_outbound(tag, user.uuid) for tag in settings.inbound_tags_list
    ]
    outbounds = [o for o in outbounds if o]  # Filter empty
    outbounds.extend(OutboundFactory.get_standard_outbounds())

    # Отдаем как ТЕКСТ (это важно для парсеров)
    return {
        "version": 2,
        "email": user.email,
        "fakedns": [{"ipPool": "198.18.0.0/16", "poolSize": 65535}],
        "dns": {
            "hosts": dns_hosts,
            "servers": DNSFactory.get_default_servers(),
            "queryStrategy": "UseIPv4",
        },
        "outbounds": outbounds,
        "routing": {"domainStrategy": "IPIfNonMatch", "rules": routing_rules},
    }


# @app.get("/v1/sub/{user_uuid}")
# async def get_subscription(user_uuid: str, session: Session = Depends(get_session)):
#     # 1. Fetch Data (Your original logic)
#     user = session.exec(select(User).where(User.uuid == user_uuid, User.is_active)).first()
#     if not user:
#         return Response(status_code=404)

#     all_users = list(session.exec(select(User)).all())
#     db_routes = list(session.exec(select(Route)).all())

#     # 2. Use your Factories
#     dns_hosts = DNSFactory.build_hosts(all_users)
#     # We convert your routing_rules (JSON) into Clash-style rules (String list)
#     clash_rules = [f"DOMAIN-SUFFIX,{settings.MESH_DOMAIN},🚀 Azenord-Mesh"]
#     for r in db_routes:
#         # Example mapping of your custom routes to Clash format
#         clash_rules.append(f"DOMAIN-KEYWORD,{r.pattern},🚀 Azenord-Mesh")
#     clash_rules.append("MATCH,DIRECT")

#     # 3. Build Outbounds
#     # We extract your outbound logic into Clash proxy format
#     proxies = []
#     for tag in settings.inbound_tags_list:
#         outbound = OutboundFactory.create_outbound(tag, user.uuid)
#         if outbound:
#             # Reformatting Xray JSON outbound to Clash Proxy YAML
#             proxy = {
#                 "name": f"Azenord-{tag}",
#                 "type": "vless",
#                 "server": settings.XRAY_DOMAIN,
#                 "port": outbound["settings"]["vnext"][0]["port"],
#                 "uuid": user.uuid,
#                 "tls": True,
#                 "servername": settings.XRAY_DOMAIN,
#                 "network": outbound["streamSettings"]["network"],
#             }
#             # Handle transport-specific opts
#             if proxy["network"] == "tcp":
#                 proxy["flow"] = "xtls-rprx-vision"
#             elif proxy["network"] == "xhttp":
#                 proxy["xhttp-opts"] = {
#                     "path": settings.XHTTP_PATH,
#                     "mode": "stream-one",
#                     "extra-alpn": outbound["streamSettings"]["tlsSettings"]["alpn"],
#                 }
#             proxies.append(proxy)

#     # 4. Final Clash Assembly (Nothing lost)
#     clash_config = {
#         "version": "2.0",  # Kept from your original
#         "email": user.email,  # Kept from your original
#         "proxies": proxies,
#         "proxy-groups": [
#             {"name": "🚀 Azenord-Mesh", "type": "select", "proxies": [p["name"] for p in proxies]}
#         ],
#         "dns": {
#             "enable": True,
#             "enhanced-mode": "fake-ip",
#             "fake-ip-range": "198.18.0.1/16",
#             "nameserver": DNSFactory.get_default_servers(),
#             "hosts": dns_hosts,  # YOUR MESH PHONEBOOK
#             "query-strategy": "UseIPv4",  # Kept from your original
#         },
#         "rules": clash_rules,
#     }

#     yaml_data = yaml.dump(clash_config, allow_unicode=True, sort_keys=False)

#     return Response(
#         content=yaml_data,
#         media_type="text/yaml",
#         headers={"Subscription-Userinfo": "upload=0;download=0;total=107374182400;expire=0"},
#     )

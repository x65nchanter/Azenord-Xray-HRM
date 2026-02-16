import base64
import json

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

    # 4. Final Assembly
    config_dict = {
        "version": "2.0",
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

    # Превращаем в строку и кодируем
    json_str = json.dumps(config_dict, indent=2)
    b64_config = base64.b64encode(json_str.encode()).decode()

    # Отдаем как ТЕКСТ (это важно для парсеров)
    return Response(content=b64_config, media_type="text/plain")

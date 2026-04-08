"""FastAPI dependencies — parse body once, enforce limit, return model for the route handler."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Body
from starlette.requests import Request

from app.core.deps import get_client_ip
from app.core.rate_limit.limiter import check_portal_limit
from app.schemas.portal import PortalPayBody, PortalRedeemBody, PortalSessionQuery


async def portal_rate_limit_pay_body(
    request: Request,
    site_slug: str,
    body: Annotated[PortalPayBody, Body()],
) -> PortalPayBody:
    ip = await get_client_ip(request)
    await check_portal_limit(
        action="pay",
        site_slug=site_slug,
        client_ip=ip,
        customer_id=body.customer_id,
        phone=body.phone,
    )
    return body


async def portal_rate_limit_redeem_body(
    request: Request,
    site_slug: str,
    body: Annotated[PortalRedeemBody, Body()],
) -> PortalRedeemBody:
    ip = await get_client_ip(request)
    await check_portal_limit(
        action="redeem",
        site_slug=site_slug,
        client_ip=ip,
        customer_id=body.customer_id,
        voucher_code=body.code,
    )
    return body


async def portal_rate_limit_access_status(
    request: Request,
    site_slug: str,
    customer_id: uuid.UUID | None = None,
    mac_address: str | None = None,
) -> None:
    ip = await get_client_ip(request)
    await check_portal_limit(
        action="status",
        site_slug=site_slug,
        client_ip=ip,
        customer_id=customer_id,
        mac_address=mac_address.upper().replace("-", ":") if mac_address else None,
    )


async def portal_rate_limit_session_body(
    request: Request,
    site_slug: str,
    body: Annotated[PortalSessionQuery, Body()],
) -> PortalSessionQuery:
    ip = await get_client_ip(request)
    mac = body.mac_address.upper().replace("-", ":")
    await check_portal_limit(
        action="status",
        site_slug=site_slug,
        client_ip=ip,
        mac_address=mac,
    )
    return body

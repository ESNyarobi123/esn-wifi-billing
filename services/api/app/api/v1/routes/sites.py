from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import DbSession, get_current_user, require_permissions
from app.core.exceptions import NotFoundError
from app.core.responses import ok
from app.db.enums import RecordStatus
from app.modules.access_control.audit_service import record_audit
from app.modules.access_control.constants import PERM_SITES_READ, PERM_SITES_WRITE
from app.modules.auth.models import User
from app.modules.portal.models import PortalBranding
from app.modules.routers.models import Site

router = APIRouter()


class SiteCreate(BaseModel):
    name: str
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    address: str | None = None
    timezone: str = "Africa/Dar_es_Salaam"


class SiteUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    timezone: str | None = None
    status: str | None = None


class PortalBrandingUpsert(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None
    welcome_message: str | None = None
    support_phone: str | None = None
    extra: dict | None = None


@router.get("/sites/{site_id}", dependencies=[Depends(require_permissions(PERM_SITES_READ))])
async def get_site(session: DbSession, site_id: uuid.UUID, _u: User = Depends(get_current_user)):
    site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    return ok(
        {
            "id": str(site.id),
            "name": site.name,
            "slug": site.slug,
            "address": site.address,
            "timezone": site.timezone,
            "status": site.status,
        },
    )


@router.get("/sites", dependencies=[Depends(require_permissions(PERM_SITES_READ))])
async def list_sites(session: DbSession, _u: User = Depends(get_current_user), include_deleted: bool = False):
    stmt = select(Site).order_by(Site.name)
    if not include_deleted:
        stmt = stmt.where(Site.status != RecordStatus.deleted.value)
    rows = (await session.execute(stmt)).scalars().all()
    return ok(
        [
            {
                "id": str(s.id),
                "name": s.name,
                "slug": s.slug,
                "address": s.address,
                "timezone": s.timezone,
                "status": s.status,
            }
            for s in rows
        ],
    )


@router.post("/sites", dependencies=[Depends(require_permissions(PERM_SITES_WRITE))])
async def create_site(session: DbSession, body: SiteCreate, admin: User = Depends(get_current_user)):
    site = Site(name=body.name, slug=body.slug, address=body.address, timezone=body.timezone)
    session.add(site)
    await session.flush()
    await record_audit(session, user_id=admin.id, action="site.create", resource_type="site", resource_id=str(site.id))
    return ok({"id": str(site.id)}, message="Site created")


@router.patch("/sites/{site_id}", dependencies=[Depends(require_permissions(PERM_SITES_WRITE))])
async def update_site(session: DbSession, site_id: uuid.UUID, body: SiteUpdate, admin: User = Depends(get_current_user)):
    site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
    if site is None:
        raise NotFoundError("Site not found")
    if body.name is not None:
        site.name = body.name
    if body.address is not None:
        site.address = body.address
    if body.timezone is not None:
        site.timezone = body.timezone
    if body.status is not None:
        site.status = body.status
    await record_audit(session, user_id=admin.id, action="site.update", resource_type="site", resource_id=str(site_id))
    return ok(message="Site updated")


@router.delete("/sites/{site_id}", dependencies=[Depends(require_permissions(PERM_SITES_WRITE))])
async def delete_site(session: DbSession, site_id: uuid.UUID, admin: User = Depends(get_current_user)):
    site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    site.status = RecordStatus.deleted.value
    await record_audit(session, user_id=admin.id, action="site.delete", resource_type="site", resource_id=str(site_id))
    return ok(message="Site deleted")


@router.put("/sites/{site_id}/portal-branding", dependencies=[Depends(require_permissions(PERM_SITES_WRITE))])
async def upsert_portal_branding(
    session: DbSession,
    site_id: uuid.UUID,
    body: PortalBrandingUpsert,
    admin: User = Depends(get_current_user),
):
    site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
    if site is None or site.status == RecordStatus.deleted.value:
        raise NotFoundError("Site not found")
    branding = (
        await session.execute(select(PortalBranding).where(PortalBranding.site_id == site_id))
    ).scalar_one_or_none()
    if branding is None:
        branding = PortalBranding(
            site_id=site_id,
            logo_url=body.logo_url,
            primary_color=body.primary_color,
            welcome_message=body.welcome_message,
            support_phone=body.support_phone,
            extra=body.extra,
        )
        session.add(branding)
    else:
        if body.logo_url is not None:
            branding.logo_url = body.logo_url
        if body.primary_color is not None:
            branding.primary_color = body.primary_color
        if body.welcome_message is not None:
            branding.welcome_message = body.welcome_message
        if body.support_phone is not None:
            branding.support_phone = body.support_phone
        if body.extra is not None:
            branding.extra = body.extra
    await session.flush()
    await record_audit(
        session,
        user_id=admin.id,
        action="site.portal_branding_upsert",
        resource_type="site",
        resource_id=str(site_id),
    )
    return ok({"id": str(branding.id)}, message="Portal branding saved")

from __future__ import annotations

import asyncio
import io
import zipfile
from ftplib import FTP, FTP_TLS, all_errors, error_perm
from pathlib import PurePosixPath
from typing import Any

from app.core.exceptions import ServiceUnavailableError
from app.core.security import decrypt_secret
from app.integrations.mikrotik.client import MikroTikClient
from app.modules.routers.models import Router
from app.modules.routers.provisioning_service import GeneratedProvisioningPackage


def _remote_uploads(package: GeneratedProvisioningPackage) -> dict[str, bytes]:
    uploads: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(package.payload)) as archive:
        for name in archive.namelist():
            if name == "README.txt":
                continue
            if name == "router-provisioning.rsc":
                uploads["router-provisioning.rsc"] = archive.read(name)
                continue
            if name.startswith("hotspot-files/"):
                rel = name.removeprefix("hotspot-files/")
                uploads[str(PurePosixPath(package.html_directory) / rel)] = archive.read(name)
    return uploads


def _ensure_dirs(ftp: FTP, remote_path: str) -> None:
    parent = str(PurePosixPath(remote_path).parent)
    if not parent or parent == ".":
        return
    current = ""
    for part in PurePosixPath(parent).parts:
        current = f"{current}/{part}" if current else part
        try:
            ftp.mkd(current)
        except error_perm as exc:
            msg = str(exc).lower()
            if "exist" in msg or "file exists" in msg:
                continue
            raise


def _upload_with_ftp_client(ftp: FTP, *, router: Router, password: str, uploads: dict[str, bytes]) -> list[str]:
    ftp.connect(router.host, 21, timeout=20)
    ftp.login(user=router.username, passwd=password)
    if isinstance(ftp, FTP_TLS):
        ftp.prot_p()
    uploaded: list[str] = []
    for remote_path, data in uploads.items():
        _ensure_dirs(ftp, remote_path)
        ftp.storbinary(f"STOR {remote_path}", io.BytesIO(data))
        uploaded.append(remote_path)
    return uploaded


def _ftp_upload(router: Router, *, password: str, uploads: dict[str, bytes]) -> list[str]:
    ftp_cls = FTP_TLS if router.use_tls else FTP
    ftp = ftp_cls()
    try:
        return _upload_with_ftp_client(ftp, router=router, password=password, uploads=uploads)
    except all_errors as exc:  # noqa: PERF203
        if router.use_tls:
            try:
                fallback = FTP()
                try:
                    return _upload_with_ftp_client(fallback, router=router, password=password, uploads=uploads)
                finally:
                    try:
                        fallback.quit()
                    except Exception:
                        try:
                            fallback.close()
                        except Exception:
                            pass
            except all_errors:
                pass
        raise RuntimeError(f"FTP upload failed: {exc}") from exc
    finally:
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass


async def push_provisioning_package_to_router(
    *,
    router: Router,
    package: GeneratedProvisioningPackage,
    import_script: bool = True,
) -> dict[str, Any]:
    try:
        password = decrypt_secret(router.password_encrypted)
        uploads = _remote_uploads(package)
        uploaded_paths = await asyncio.to_thread(_ftp_upload, router, password=password, uploads=uploads)

        client = MikroTikClient(
            host=router.host,
            username=router.username,
            password=password,
            port=router.api_port,
            use_tls=router.use_tls,
        )
        imported = False
        if import_script:
            await client.call("/import", attributes={"file-name": "router-provisioning.rsc"})
            imported = True

        verification = await _verify_provisioning(client=client, package=package)
        return {
            "uploaded_paths": uploaded_paths,
            "uploaded_count": len(uploaded_paths),
            "imported": imported,
            "verification": verification,
        }
    except ServiceUnavailableError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Provisioning push failed: {exc}") from exc


async def _verify_provisioning(*, client: MikroTikClient, package: GeneratedProvisioningPackage) -> dict[str, Any]:
    resource_res, profile_res, hotspot_res, dns_res = await client.call_many(
        [
            (
                "/system/resource/print",
                {".proplist": "uptime,version,board-name"},
                None,
            ),
            (
                "/ip/hotspot/profile/print",
                {".proplist": "name,dns-name,html-directory,ssl-login"},
                [f"name={package.hotspot_profile_name}"],
            ),
            (
                "/ip/hotspot/print",
                {".proplist": "name,profile,disabled"},
                [f"name={package.hotspot_server_name}"],
            ),
            (
                "/ip/dns/static/print",
                {".proplist": "name,address,comment"},
                [f"name={package.dns_name}"],
            ),
        ],
    )
    profile = profile_res.rows[0] if profile_res.rows else None
    hotspot = hotspot_res.rows[0] if hotspot_res.rows else None
    dns_record = dns_res.rows[0] if dns_res.rows else None
    resources = resource_res.rows[0] if resource_res.rows else {}
    return {
        "router": {
            "board_name": resources.get("board-name"),
            "version": resources.get("version"),
            "uptime": resources.get("uptime"),
        },
        "hotspot_profile": profile,
        "hotspot_server": hotspot,
        "dns_static": dns_record,
    }

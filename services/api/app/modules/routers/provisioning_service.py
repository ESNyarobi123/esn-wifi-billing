from __future__ import annotations

import html
import ipaddress
import io
import re
import zipfile
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.modules.portal.models import PortalBranding
from app.modules.routers.models import Router, Site

DEFAULT_PORTAL_BASE_URL = "http://localhost:3000"
DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_HOTSPOT_INTERFACE = "bridge-hotspot"
DEFAULT_WAN_INTERFACE = "ether1"
DEFAULT_LAN_CIDR = "10.10.10.1/24"
DEFAULT_POOL_START = "10.10.10.10"
DEFAULT_POOL_END = "10.10.10.250"
DEFAULT_ACCENT = "#FBA002"


@dataclass(slots=True)
class RouterProvisioningOptions:
    portal_base_url: str | None = None
    api_base_url: str | None = None
    dns_name: str | None = None
    hotspot_interface: str = DEFAULT_HOTSPOT_INTERFACE
    wan_interface: str = DEFAULT_WAN_INTERFACE
    lan_cidr: str = DEFAULT_LAN_CIDR
    dhcp_pool_start: str = DEFAULT_POOL_START
    dhcp_pool_end: str = DEFAULT_POOL_END
    hotspot_html_directory: str | None = None
    hotspot_server_name: str | None = None
    hotspot_profile_name: str | None = None
    hotspot_user_profile_name: str | None = None
    address_pool_name: str | None = None
    dhcp_server_name: str | None = None
    ssl_certificate_name: str | None = None
    extra_walled_garden_hosts: tuple[str, ...] = ()
    provider_templates: tuple[str, ...] = ()
    auto_dns_static: bool = True
    auto_issue_letsencrypt: bool = False


@dataclass(slots=True)
class GeneratedProvisioningPackage:
    filename: str
    payload: bytes
    script: str
    html_directory: str
    portal_url: str
    api_url: str
    dns_name: str
    hotspot_server_name: str
    hotspot_profile_name: str
    walled_garden_hosts: tuple[str, ...]


@dataclass(slots=True)
class _ResolvedOptions:
    portal_base_url: str
    api_base_url: str
    portal_url: str
    portal_access_url: str
    portal_session_url: str
    dns_name: str
    hotspot_interface: str
    wan_interface: str
    lan_cidr: str
    lan_network_cidr: str
    gateway_ip: str
    dhcp_pool_start: str
    dhcp_pool_end: str
    hotspot_html_directory: str
    hotspot_server_name: str
    hotspot_profile_name: str
    hotspot_user_profile_name: str
    address_pool_name: str
    dhcp_server_name: str
    ssl_certificate_name: str
    walled_garden_hosts: tuple[str, ...]
    provider_templates: tuple[str, ...]
    auto_dns_static: bool
    auto_issue_letsencrypt: bool


def _flash_directory(path: str) -> str:
    cleaned = path.strip().strip("/")
    if cleaned.startswith("flash/"):
        return cleaned
    return f"flash/{cleaned}"


def build_router_provisioning_package(
    *,
    router: Router,
    site: Site,
    branding: PortalBranding | None,
    public_settings: dict[str, Any],
    options: RouterProvisioningOptions,
) -> GeneratedProvisioningPackage:
    resolved = _resolve_options(site=site, branding=branding, options=options)
    company_name = _company_name(public_settings) or site.name or "ESN WiFi"
    support_email = _support_email(public_settings) or "support@example.com"
    support_phone = (branding.support_phone if branding else None) or ""
    welcome_message = (branding.welcome_message if branding else None) or f"Welcome to {company_name}"
    accent = _sanitize_color((branding.primary_color if branding else None) or DEFAULT_ACCENT)
    script = _build_routeros_script(
        router=router,
        site=site,
        company_name=company_name,
        support_email=support_email,
        support_phone=support_phone,
        resolved=resolved,
    )
    files = _build_hotspot_files(
        router=router,
        site=site,
        company_name=company_name,
        welcome_message=welcome_message,
        accent=accent,
        resolved=resolved,
    )
    package_name = f"esn-provisioning-{_slugify(site.slug)}-{_slugify(router.name)}.zip"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _build_readme(site=site, router=router, resolved=resolved))
        zf.writestr("router-provisioning.rsc", script)
        for path, content in files.items():
            zf.writestr(path, content)
    return GeneratedProvisioningPackage(
        filename=package_name,
        payload=archive.getvalue(),
        script=script,
        html_directory=resolved.hotspot_html_directory,
        portal_url=resolved.portal_url,
        api_url=resolved.api_base_url,
        dns_name=resolved.dns_name,
        hotspot_server_name=resolved.hotspot_server_name,
        hotspot_profile_name=resolved.hotspot_profile_name,
        walled_garden_hosts=resolved.walled_garden_hosts,
    )


def _resolve_options(
    *,
    site: Site,
    branding: PortalBranding | None,
    options: RouterProvisioningOptions,
) -> _ResolvedOptions:
    portal_base_url = _normalize_base_url(options.portal_base_url or DEFAULT_PORTAL_BASE_URL, "portal base URL")
    api_base_url = _normalize_base_url(options.api_base_url or DEFAULT_API_BASE_URL, "API base URL")
    hotspot_interface = _require_text(options.hotspot_interface, "HotSpot interface")
    wan_interface = _require_text(options.wan_interface, "WAN interface")
    network = _parse_ipv4_network(options.lan_cidr)
    pool_start = _parse_ipv4_address(options.dhcp_pool_start, "DHCP pool start")
    pool_end = _parse_ipv4_address(options.dhcp_pool_end, "DHCP pool end")
    if pool_start not in network or pool_end not in network:
        raise ValidationAppError("DHCP pool must stay inside the selected LAN subnet.")
    if int(pool_start) >= int(pool_end):
        raise ValidationAppError("DHCP pool start must be before the end address.")

    slug = _slugify(site.slug or "site")
    dns_name = _normalize_dns_name(options.dns_name or f"login.{slug}.wifi.local")
    hotspot_html_directory = _require_text(
        options.hotspot_html_directory or f"esn-hotspot-{slug}",
        "HotSpot HTML directory",
    )
    hotspot_server_name = _require_text(options.hotspot_server_name or f"esn-hotspot-{slug}", "HotSpot server name")
    hotspot_profile_name = _require_text(options.hotspot_profile_name or f"esn-profile-{slug}", "HotSpot profile name")
    hotspot_user_profile_name = _require_text(
        options.hotspot_user_profile_name or f"esn-users-{slug}",
        "HotSpot user profile name",
    )
    address_pool_name = _require_text(options.address_pool_name or f"esn-pool-{slug}", "Address pool name")
    dhcp_server_name = _require_text(options.dhcp_server_name or f"esn-dhcp-{slug}", "DHCP server name")
    ssl_certificate_name = (options.ssl_certificate_name or "").strip()

    portal_url = f"{portal_base_url}/{site.slug}"
    portal_access_url = f"{portal_url}/access"
    portal_session_url = f"{portal_url}/session"

    hosts = {
        _host_from_url(portal_base_url, "portal base URL"),
        _host_from_url(api_base_url, "API base URL"),
    }
    for raw in options.extra_walled_garden_hosts:
        host = _normalize_host(raw)
        if host:
            hosts.add(host)
    provider_templates = tuple(sorted({_slugify(x) for x in options.provider_templates if _slugify(x)}))
    for host in _provider_template_hosts(provider_templates):
        hosts.add(host)
    if branding and branding.logo_url:
        logo_host = _host_from_maybe_url(branding.logo_url)
        if logo_host:
            hosts.add(logo_host)

    return _ResolvedOptions(
        portal_base_url=portal_base_url,
        api_base_url=api_base_url,
        portal_url=portal_url,
        portal_access_url=portal_access_url,
        portal_session_url=portal_session_url,
        dns_name=dns_name,
        hotspot_interface=hotspot_interface,
        wan_interface=wan_interface,
        lan_cidr=str(ipaddress.IPv4Interface(options.lan_cidr).with_prefixlen),
        lan_network_cidr=str(network),
        gateway_ip=str(ipaddress.IPv4Interface(options.lan_cidr).ip),
        dhcp_pool_start=str(pool_start),
        dhcp_pool_end=str(pool_end),
        hotspot_html_directory=hotspot_html_directory,
        hotspot_server_name=hotspot_server_name,
        hotspot_profile_name=hotspot_profile_name,
        hotspot_user_profile_name=hotspot_user_profile_name,
        address_pool_name=address_pool_name,
        dhcp_server_name=dhcp_server_name,
        ssl_certificate_name=ssl_certificate_name,
        walled_garden_hosts=tuple(sorted(hosts)),
        provider_templates=provider_templates,
        auto_dns_static=bool(options.auto_dns_static),
        auto_issue_letsencrypt=bool(options.auto_issue_letsencrypt),
    )


def _build_routeros_script(
    *,
    router: Router,
    site: Site,
    company_name: str,
    support_email: str,
    support_phone: str,
    resolved: _ResolvedOptions,
) -> str:
    host_rules = []
    ip_rules = []
    for host in resolved.walled_garden_hosts:
        if _is_ip_literal(host):
            comment = f"ESN portal IP {host}"
            ip_rules.append(
                f':if ([:len [/ip hotspot walled-garden ip find where server=$hotspotServerName and comment={_rsc(comment)}]] = 0) do={{ '
                f'/ip hotspot walled-garden ip add server=$hotspotServerName action=accept dst-address={_rsc(host)} comment={_rsc(comment)}; '
                f'}};'
            )
        else:
            comment = f"ESN portal host {host}"
            host_rules.append(
                f':if ([:len [/ip hotspot walled-garden find where server=$hotspotServerName and comment={_rsc(comment)}]] = 0) do={{ '
                f'/ip hotspot walled-garden add server=$hotspotServerName dst-host={_rsc(host)} comment={_rsc(comment)}; '
                f'}};'
            )
    host_rules_text = "\n".join([*ip_rules, *host_rules])
    dns_static_block = ""
    if resolved.auto_dns_static:
        dns_static_block = f"""
:local dnsStaticId [/ip dns static find where name=$dnsName];
:if ([:len $dnsStaticId] = 0) do={{
  /ip dns static add name=$dnsName address=$gatewayIp ttl=1m comment={_rsc("ESN captive portal DNS")};
}} else={{
  /ip dns static set numbers=$dnsStaticId address=$gatewayIp ttl=1m comment={_rsc("ESN captive portal DNS")};
}}
"""
    letsencrypt_block = ""
    if resolved.auto_issue_letsencrypt:
        letsencrypt_block = """
:put ("[ESN] Attempting Let's Encrypt issuance for " . $dnsName);
/certificate enable-ssl-certificate dns-name=$dnsName
:local acmeCertId [/certificate find where common-name=$dnsName && trusted=yes];
:if ([:len $acmeCertId] > 0) do={
  /ip hotspot profile set numbers=$hotspotProfileId ssl-certificate=$acmeCertId;
  :put "[ESN] Let's Encrypt certificate applied to HotSpot profile.";
} else={
  :put "[ESN] Let's Encrypt did not return a trusted certificate. Check public DNS, WAN reachability, and port 80.";
}
"""

    return f"""# ESN WiFi Billing HotSpot provisioning
# Router: {router.name}
# Site: {site.name} ({site.slug})
# Generated for external portal redirect + branded captive pages.
#
# Before import:
# 1. Upload the bundled hotspot-files directory to router files storage.
# 2. If your router has persistent flash storage, use htmlDirectory "{_flash_directory(resolved.hotspot_html_directory)}".
# 3. Confirm hotspotInterface / wanInterface / dnsName values below match your network.
#
# ESN can authorize RouterOS hotspot users directly after payment/redeem.
# If you move to external RADIUS later, this captive portal package still remains valid.

:local hotspotInterface {_rsc(resolved.hotspot_interface)};
:local wanInterface {_rsc(resolved.wan_interface)};
:local lanCidr {_rsc(resolved.lan_cidr)};
:local lanNetwork {_rsc(resolved.lan_network_cidr)};
:local gatewayIp {_rsc(resolved.gateway_ip)};
:local poolName {_rsc(resolved.address_pool_name)};
:local poolRange {_rsc(f"{resolved.dhcp_pool_start}-{resolved.dhcp_pool_end}")};
:local dhcpName {_rsc(resolved.dhcp_server_name)};
:local hotspotServerName {_rsc(resolved.hotspot_server_name)};
:local hotspotProfileName {_rsc(resolved.hotspot_profile_name)};
:local hotspotUserProfileName {_rsc(resolved.hotspot_user_profile_name)};
:local htmlDirectory {_rsc(resolved.hotspot_html_directory)};
:local dnsName {_rsc(resolved.dns_name)};
:local sslCertificate {_rsc(resolved.ssl_certificate_name)};

:put ("[ESN] Preparing hotspot for {site.slug} -> " . $hotspotInterface);
:put ("[ESN] Portal URL: {resolved.portal_url}");
:put ("[ESN] API URL: {resolved.api_base_url}");

/ip dns set allow-remote-requests=yes
{dns_static_block}

:local poolId [/ip pool find where name=$poolName];
:if ([:len $poolId] = 0) do={{
  /ip pool add name=$poolName ranges=$poolRange;
}} else={{
  /ip pool set numbers=$poolId ranges=$poolRange;
}}

:if ([:len [/ip address find where interface=$hotspotInterface and address=$lanCidr]] = 0) do={{
  /ip address add address=$lanCidr interface=$hotspotInterface comment={_rsc("ESN hotspot gateway")};
}}

:local dhcpNetId [/ip dhcp-server network find where address=$lanNetwork];
:if ([:len $dhcpNetId] = 0) do={{
  /ip dhcp-server network add address=$lanNetwork gateway=$gatewayIp dns-server=$gatewayIp comment={_rsc("ESN captive portal subnet")};
}} else={{
  /ip dhcp-server network set numbers=$dhcpNetId gateway=$gatewayIp dns-server=$gatewayIp;
}}

:local dhcpId [/ip dhcp-server find where name=$dhcpName];
:if ([:len $dhcpId] = 0) do={{
  /ip dhcp-server add name=$dhcpName interface=$hotspotInterface address-pool=$poolName lease-time=1h disabled=no;
}} else={{
  /ip dhcp-server set numbers=$dhcpId interface=$hotspotInterface address-pool=$poolName lease-time=1h disabled=no;
}}

:if ([:len [/ip firewall nat find where chain="srcnat" out-interface=$wanInterface action="masquerade" comment={_rsc("ESN hotspot masquerade")}]] = 0) do={{
  /ip firewall nat add chain=srcnat out-interface=$wanInterface action=masquerade comment={_rsc("ESN hotspot masquerade")};
}}

:local hotspotUserProfileId [/ip hotspot user profile find where name=$hotspotUserProfileName];
:if ([:len $hotspotUserProfileId] = 0) do={{
  /ip hotspot user profile add name=$hotspotUserProfileName shared-users=1 idle-timeout=10m keepalive-timeout=2m status-autorefresh=1m transparent-proxy=no add-mac-cookie=yes;
  :set hotspotUserProfileId [/ip hotspot user profile find where name=$hotspotUserProfileName];
}} else={{
  /ip hotspot user profile set numbers=$hotspotUserProfileId shared-users=1 idle-timeout=10m keepalive-timeout=2m status-autorefresh=1m transparent-proxy=no add-mac-cookie=yes;
}}

:local hotspotProfileId [/ip hotspot profile find where name=$hotspotProfileName];
:if ([:len $hotspotProfileId] = 0) do={{
  /ip hotspot profile add name=$hotspotProfileName hotspot-address=$gatewayIp dns-name=$dnsName html-directory=$htmlDirectory login-by={_rsc("http-pap,http-chap,cookie,mac-cookie")} http-cookie-lifetime=1d;
  :set hotspotProfileId [/ip hotspot profile find where name=$hotspotProfileName];
}} else={{
  /ip hotspot profile set numbers=$hotspotProfileId hotspot-address=$gatewayIp dns-name=$dnsName html-directory=$htmlDirectory login-by={_rsc("http-pap,http-chap,cookie,mac-cookie")} http-cookie-lifetime=1d;
}}

:if ([:len $sslCertificate] > 0) do={{
  /ip hotspot profile set numbers=$hotspotProfileId ssl-certificate=$sslCertificate;
}} else={{
  /ip hotspot profile set numbers=$hotspotProfileId ssl-certificate=none;
}}
{letsencrypt_block}

:local hotspotId [/ip hotspot find where name=$hotspotServerName];
:if ([:len $hotspotId] = 0) do={{
  /ip hotspot add name=$hotspotServerName interface=$hotspotInterface address-pool=$poolName profile=$hotspotProfileName idle-timeout=5m keepalive-timeout=2m disabled=no;
}} else={{
  /ip hotspot set numbers=$hotspotId interface=$hotspotInterface address-pool=$poolName profile=$hotspotProfileName idle-timeout=5m keepalive-timeout=2m disabled=no;
}}

{host_rules_text}

:put "[ESN] Provisioning applied.";
:put ("[ESN] Captive pages directory: " . $htmlDirectory);
:put "[ESN] Next: upload hotspot-files, test popup redirect, then verify ESN authorization on a paid device.";
:put ("[ESN] Support contact: {support_phone or support_email}");
:put ("[ESN] Brand: {company_name}");
"""


def _build_hotspot_files(
    *,
    router: Router,
    site: Site,
    company_name: str,
    welcome_message: str,
    accent: str,
    resolved: _ResolvedOptions,
) -> dict[str, str]:
    portal_action = html.escape(resolved.portal_url, quote=True)
    access_action = html.escape(resolved.portal_access_url, quote=True)
    session_action = html.escape(resolved.portal_session_url, quote=True)
    brand = html.escape(company_name)
    venue = html.escape(site.name)
    welcome = html.escape(welcome_message)
    accent_esc = html.escape(accent, quote=True)
    context_inputs = f"""
      <input type="hidden" name="hs_mac" value="$(mac)">
      <input type="hidden" name="hs_ip" value="$(ip)">
      <input type="hidden" name="hs_server" value="$(server-name)">
      <input type="hidden" name="hs_identity" value="$(identity)">
      <input type="hidden" name="hs_dst" value="$(link-orig-esc)">
      <input type="hidden" name="hs_login_url" value="$(link-login-only)">
      <input type="hidden" name="hs_status_url" value="$(link-status)">
      <input type="hidden" name="hs_error" value="$(error)">
      <input type="hidden" name="esn_router_id" value="{router.id}">
      <input type="hidden" name="esn_site_id" value="{site.id}">
    """

    def page(title: str, eyebrow: str, body: str) -> str:
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
  <style>:root{{--portal-accent:{accent_esc};}}</style>
</head>
<body>
  <main class="shell">
    <section class="panel">
      <img src="logo.svg" alt="{brand}" class="logo">
      <p class="eyebrow">{html.escape(eyebrow)}</p>
      <h1>{html.escape(title)}</h1>
      <p class="lede">{welcome}</p>
      {body}
    </section>
  </main>
</body>
</html>
"""

    redirect_body = f"""
      <form id="portal-redirect" action="{portal_action}" method="get">
        {context_inputs}
        <button type="submit" class="primary">Open ESN portal</button>
      </form>
      <p class="muted">If nothing happens automatically, tap the button above to continue.</p>
      <script>document.getElementById("portal-redirect").submit();</script>
    """

    login_body = f"""
      <div class="stack">
        <p class="chip">Venue: {venue}</p>
        <p class="muted">This router is prepared for the ESN payment portal. We detected your device and will carry the hotspot context into the web flow.</p>
      </div>
      <form id="portal-login" action="{portal_action}" method="get">
        {context_inputs}
        <button type="submit" class="primary">Continue to sign in</button>
      </form>
      <p class="fineprint">Router login page: <span class="mono">$(link-login-only)</span></p>
      <script>document.getElementById("portal-login").submit();</script>
    """

    alogin_body = f"""
      <div class="stack">
        <p class="chip success">Hotspot session detected</p>
        <p class="muted">If this session was created by ESN billing, you can confirm your remaining access below.</p>
      </div>
      <form id="portal-access" action="{access_action}" method="get">
        {context_inputs}
        <button type="submit" class="primary">Check access in ESN portal</button>
      </form>
      <div class="actions">
        <a class="secondary" href="$(link-status)">View router session</a>
      </div>
      <script>document.getElementById("portal-access").submit();</script>
    """

    status_body = f"""
      <div class="stats">
        <div><span>Device MAC</span><strong class="mono">$(mac)</strong></div>
        <div><span>Assigned IP</span><strong class="mono">$(ip)</strong></div>
        <div><span>Time left</span><strong>$(session-time-left)</strong></div>
        <div><span>Session uptime</span><strong>$(uptime)</strong></div>
        <div><span>Download</span><strong>$(bytes-out-nice)</strong></div>
        <div><span>Upload</span><strong>$(bytes-in-nice)</strong></div>
      </div>
      <div class="actions">
        <a class="primary" href="{session_action}?hs_mac=$(mac)">Open ESN session page</a>
        <a class="secondary" href="$(link-logout)">Disconnect</a>
      </div>
    """

    logout_body = f"""
      <p class="muted">Your router session has ended. You can return to the ESN portal to buy another plan or confirm account status.</p>
      <div class="actions">
        <a class="primary" href="{portal_action}">Back to portal</a>
        <a class="secondary" href="$(link-login-only)">Router login page</a>
      </div>
    """

    error_body = f"""
      <p class="muted">The hotspot reported: <span class="mono">$(error)</span></p>
      <form action="{portal_action}" method="get">
        {context_inputs}
        <button type="submit" class="primary">Retry in ESN portal</button>
      </form>
    """

    fstatus_body = f"""
      <p class="muted">This device is not authenticated yet. Return to the ESN portal to pay, redeem, or view available plans.</p>
      <div class="actions">
        <a class="primary" href="{portal_action}">Open portal</a>
        <a class="secondary" href="$(link-login-only)">Router login</a>
      </div>
    """

    api_payload = f"""{{
  "captive": $(if logged-in == 'yes')false$(else)true$(endif),
  "user-portal-url": "$(link-login-only)",
  "venue-info-url": "{resolved.portal_url}",
  $(if session-timeout-secs != 0)"seconds-remaining": $(session-timeout-secs),$(endif)
  $(if remain-bytes-total)"bytes-remaining": $(remain-bytes-total),$(endif)
  "can-extend-session": true
}}
"""

    styles = """
:root {
  color-scheme: dark;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at top, color-mix(in srgb, var(--portal-accent) 18%, transparent), transparent 38%),
    linear-gradient(180deg, #10150e 0%, #182019 45%, #0f140f 100%);
  color: #f7f8f4;
}

.shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 1.5rem;
}

.panel {
  width: min(100%, 32rem);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 1.5rem;
  background: rgba(15, 18, 14, 0.88);
  box-shadow: 0 32px 64px rgba(0, 0, 0, 0.32);
  padding: 1.5rem;
  backdrop-filter: blur(14px);
}

.logo {
  width: 100%;
  max-width: 11rem;
  display: block;
  margin-bottom: 1rem;
}

.eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.56);
}

h1 {
  margin: 0.35rem 0 0;
  font-size: clamp(1.6rem, 4vw, 2.1rem);
  line-height: 1.05;
}

.lede,
.muted,
.fineprint {
  color: rgba(255, 255, 255, 0.74);
}

.lede {
  margin: 0.75rem 0 1.1rem;
  line-height: 1.55;
}

.muted,
.fineprint {
  font-size: 0.92rem;
  line-height: 1.5;
}

.fineprint {
  margin-top: 0.85rem;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Consolas, monospace;
  word-break: break-all;
}

.primary,
.secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 3rem;
  width: 100%;
  border-radius: 999px;
  text-decoration: none;
  font-weight: 700;
  border: 0;
  cursor: pointer;
  padding: 0.85rem 1.1rem;
}

.primary {
  background: var(--portal-accent);
  color: #12150f;
}

.secondary {
  background: rgba(255, 255, 255, 0.06);
  color: #f7f8f4;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.actions,
.stack {
  display: grid;
  gap: 0.8rem;
}

.chip {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 0.4rem 0.75rem;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.82rem;
}

.chip.success {
  background: rgba(78, 212, 156, 0.14);
  color: #9cf2c5;
}

.stats {
  display: grid;
  gap: 0.85rem;
  margin: 1.2rem 0;
}

.stats div {
  padding: 0.9rem 1rem;
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.stats span {
  display: block;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.58);
  margin-bottom: 0.35rem;
}

.stats strong {
  display: block;
  font-size: 1rem;
}
"""

    logo = f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="120" viewBox="0 0 360 120" role="img" aria-labelledby="title desc">
  <title id="title">{brand}</title>
  <desc id="desc">Generated ESN hotspot logo for {venue}</desc>
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{accent_esc}" />
      <stop offset="100%" stop-color="#ffe4a3" />
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="360" height="120" rx="26" fill="#121611" />
  <rect x="16" y="16" width="88" height="88" rx="24" fill="url(#g)" />
  <text x="60" y="71" text-anchor="middle" font-family="Arial, sans-serif" font-size="32" font-weight="700" fill="#11160f">ESN</text>
  <text x="126" y="56" font-family="Arial, sans-serif" font-size="26" font-weight="700" fill="#f7f8f4">{brand}</text>
  <text x="126" y="84" font-family="Arial, sans-serif" font-size="16" fill="#b8beb4">{venue}</text>
</svg>
"""

    return {
        "hotspot-files/login.html": page("Sign in to network", "ESN captive portal", login_body),
        "hotspot-files/redirect.html": page("Open ESN portal", "Captive portal redirect", redirect_body),
        "hotspot-files/rlogin.html": page("Continue to portal", "Captive portal redirect", redirect_body),
        "hotspot-files/flogin.html": page("Router sign-in issue", "HotSpot authentication", error_body),
        "hotspot-files/alogin.html": page("You are online", "HotSpot session", alogin_body),
        "hotspot-files/status.html": page("Connection status", "HotSpot session", status_body),
        "hotspot-files/fstatus.html": page("Session not active", "HotSpot session", fstatus_body),
        "hotspot-files/logout.html": page("Session ended", "HotSpot logout", logout_body),
        "hotspot-files/error.html": page("Router needs attention", "HotSpot error", error_body),
        "hotspot-files/api": api_payload,
        "hotspot-files/errors.txt": "invalid username or password=Return to the ESN portal and confirm your paid access.\n",
        "hotspot-files/styles.css": styles.lstrip(),
        "hotspot-files/logo.svg": logo,
    }


def _build_readme(*, site: Site, router: Router, resolved: _ResolvedOptions) -> str:
    host_list = "\n".join(f"  - {host}" for host in resolved.walled_garden_hosts)
    cert_step = (
        f'4. If you already have a certificate on the router, keep `sslCertificate="{resolved.ssl_certificate_name}"` in the script.\n'
        if resolved.ssl_certificate_name
        else (
            '4. The script can issue a Let’s Encrypt certificate automatically if public DNS for the hotspot name resolves to this router and port 80 is reachable.\n'
            if resolved.auto_issue_letsencrypt
            else '4. For the OS "Sign in to network" popup to behave reliably, add a valid certificate and set `sslCertificate` in the script.\n'
        )
    )
    return f"""ESN WiFi Billing router provisioning package
===========================================

Router: {router.name}
Site: {site.name} ({site.slug})

What is inside
--------------
- `router-provisioning.rsc`: RouterOS import script for HotSpot, DHCP, NAT, and walled garden.
- `hotspot-files/`: branded captive portal pages that forward users into the ESN web portal.

Recommended import flow
-----------------------
1. Review `router-provisioning.rsc` and adjust interface names if your HotSpot bridge / WAN names differ.
2. Upload the full `hotspot-files/` directory into RouterOS Files.
3. If your device has persistent flash storage, move that directory under `flash/` and change:
   `htmlDirectory="{resolved.hotspot_html_directory}"`
   to:
   `htmlDirectory="{_flash_directory(resolved.hotspot_html_directory)}"`
4. Import the script on the router:
   `/import file-name=router-provisioning.rsc`
{cert_step}5. Connect a device to Wi-Fi and confirm it lands on:
   {resolved.portal_url}

Generated defaults
------------------
- HotSpot interface: {resolved.hotspot_interface}
- WAN interface: {resolved.wan_interface}
- LAN subnet: {resolved.lan_cidr}
- DHCP pool: {resolved.dhcp_pool_start} - {resolved.dhcp_pool_end}
- HotSpot DNS name: {resolved.dns_name}
- HotSpot HTML directory: {resolved.hotspot_html_directory}

Walled garden hosts
-------------------
{host_list}

Important note
--------------
This package prepares captive portal branding, DNS, and router onboarding safely.
The ESN app can now authorize hotspot users on RouterOS directly for payment/voucher flows.
If you later switch to external RADIUS, keep the same captive portal package and replace the
local authorization layer with your chosen RADIUS server + secrets.
"""


def _provider_template_hosts(templates: tuple[str, ...]) -> set[str]:
    hosts: set[str] = set()
    for item in templates:
        if item == "clickpesa":
            host = _host_from_maybe_url(settings.clickpesa_api_base_url)
            if host:
                hosts.add(host)
    return hosts


def _company_name(settings: dict[str, Any]) -> str | None:
    raw = settings.get("company_name")
    if isinstance(raw, dict):
        name = raw.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _support_email(settings: dict[str, Any]) -> str | None:
    raw = settings.get("support_email")
    if isinstance(raw, dict):
        email_value = raw.get("email")
        if isinstance(email_value, str) and email_value.strip():
            return email_value.strip()
    return None


def _sanitize_color(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return value.upper()
    return DEFAULT_ACCENT


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "esn"


def _require_text(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationAppError(f"{label} is required.")
    return cleaned


def _normalize_base_url(value: str, label: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationAppError(f"{label} must be a full http(s) URL.")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _host_from_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if not parsed.hostname:
        raise ValidationAppError(f"{label} must include a hostname.")
    return parsed.hostname


def _host_from_maybe_url(value: str) -> str | None:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    return parsed.hostname


def _is_ip_literal(value: str) -> bool:
    try:
        ipaddress.ip_address((value or "").strip())
        return True
    except ValueError:
        return False


def _normalize_host(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if "://" in cleaned:
        return _host_from_url(cleaned, "extra walled-garden host")
    if re.fullmatch(r"[A-Za-z0-9.-]+", cleaned):
        return cleaned
    raise ValidationAppError("Extra walled-garden hosts must be plain hostnames or full URLs.")


def _normalize_dns_name(value: str) -> str:
    cleaned = value.strip().strip(".")
    if not cleaned or "." not in cleaned or len(cleaned) > 253:
        raise ValidationAppError("DNS name must be a fully qualified hostname, for example login.example.com.")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", cleaned):
        raise ValidationAppError("DNS name may only contain letters, numbers, dots, and hyphens.")
    return cleaned.lower()


def _parse_ipv4_network(value: str) -> ipaddress.IPv4Network:
    try:
        interface = ipaddress.IPv4Interface(value.strip())
    except ValueError as exc:
        raise ValidationAppError("LAN CIDR must look like 10.10.10.1/24.") from exc
    return interface.network


def _parse_ipv4_address(value: str, label: str) -> ipaddress.IPv4Address:
    try:
        return ipaddress.IPv4Address(value.strip())
    except ValueError as exc:
        raise ValidationAppError(f"{label} must be a valid IPv4 address.") from exc


def _rsc(value: str) -> str:
    return f'"{value.replace("\\\\", "\\\\\\\\").replace("\"", "\\\\\"")}"'

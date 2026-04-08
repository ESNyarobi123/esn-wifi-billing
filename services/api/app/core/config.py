from functools import cached_property

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_env: str = "development"
    # Include localhost and 127.0.0.1 — browsers treat them as different origins for CORS.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    database_url: str = "postgresql+asyncpg://esn:esn@localhost:5432/esn_wifi"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7

    router_credentials_fernet_key: str = ""
    """Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""""

    mikrotik_use_mock: bool = True
    mikrotik_use_routeros_rest_stub: bool = False
    """When true (and mock false), use ``RouterOSRestAdapterStub`` until REST/ API client is implemented."""
    mikrotik_default_api_port: int = 8728

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Payments — ClickPesa (optional in dev)
    clickpesa_enabled: bool = False
    clickpesa_api_base_url: str = "https://api.clickpesa.com"
    clickpesa_client_id: str = ""
    clickpesa_api_key: str = ""
    clickpesa_client_secret: str = ""
    clickpesa_checksum_key: str = ""
    clickpesa_webhook_path: str = "/api/v1/payments/webhooks/clickpesa"

    default_payment_provider: str = "mock"

    router_offline_after_seconds: int = 900
    """If ``last_seen_at`` is older than this, background health marks the NAS offline."""

    portal_public_setting_keys: str = "company_name,support_email"
    """Comma-separated ``system_settings`` keys safe to expose on public portal."""

    trusted_hosts: str = ""
    """Comma-separated hostnames for ``TrustedHostMiddleware`` (empty = disabled)."""

    portal_rate_limit_backend: str = "redis"
    """``redis`` (distributed, default) or ``memory`` (single-process / dev)."""

    portal_rate_limit_redis_key_prefix: str = "esn:rl"
    portal_rate_limit_redis_fail_open: bool = True
    """If True, Redis errors fall back to in-memory limiter for that process (logged). If False, return HTTP 503."""

    portal_rate_limit_redeem_per_minute: int = 40
    portal_rate_limit_pay_per_minute: int = 25
    portal_rate_limit_status_per_minute: int = 120
    """Max requests **per window** below (0 disables that action). Names retain ``_per_minute`` for env compatibility."""

    portal_rate_limit_redeem_window_seconds: int = 60
    portal_rate_limit_pay_window_seconds: int = 60
    portal_rate_limit_status_window_seconds: int = 60
    """Sliding-window span in seconds (e.g. set pay window to 300 for a 5-minute bucket)."""

    pending_payment_abandon_hours: int = 72
    """Reconciliation marks stale ``pending`` payments as ``cancelled`` after this age."""

    mikrotik_command_timeout_seconds: float = 25.0
    mikrotik_max_retries: int = 2
    """Outbound NAS command timeout and retries (real adapter only; mock bypasses)."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        u = self.database_url
        return u.replace("postgresql+asyncpg", "postgresql")

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @cached_property
    def portal_public_setting_keys_list(self) -> list[str]:
        return [k.strip() for k in self.portal_public_setting_keys.split(",") if k.strip()]

    @cached_property
    def trusted_hosts_list(self) -> list[str]:
        parts = [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]
        return parts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def clickpesa_effective_api_key(self) -> str:
        return (self.clickpesa_api_key or self.clickpesa_client_secret).strip()


settings = Settings()

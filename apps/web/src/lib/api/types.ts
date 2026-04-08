/** Standard API envelope from FastAPI `ok()` / `err()` */

export type ApiSuccess<T> = {
  success: true;
  message: string;
  data?: T;
};

export type ApiErrorBody = {
  success: false;
  message: string;
  code?: string;
  errors?: unknown;
};

export type UserPublic = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export type AnalyticsOverview = {
  revenue: {
    today: string;
    week_to_date: string;
    month_to_date: string;
    period: { from: string; to: string; total: string };
  };
  sessions: {
    active: number;
    expired: number;
    terminated: number;
    suspicious: number;
  };
  payments_by_status: Record<string, number>;
  customers: {
    new_in_period: number;
    total_customers: number;
    period: { from: string; to: string };
  };
  top_plans: { plan_id: string; name: string | null; purchases: number }[];
  routers: {
    router_id: string;
    name: string;
    is_online: boolean;
    last_seen_at: string | null;
    active_sessions: number;
    latest_snapshot: {
      cpu_load_percent: number | null;
      free_memory_bytes: number | null;
      uptime_seconds: number | null;
      created_at: string;
    } | null;
  }[];
};

export type NotificationRow = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  read_at: string | null;
  created_at: string;
};

export type RouterRow = {
  id: string;
  site_id: string;
  name: string;
  host: string;
  api_port: number;
  use_tls: boolean;
  status: string;
  is_online: boolean;
  last_seen_at: string | null;
};

export type CustomerListRow = {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  account_status: string;
  site_id: string | null;
};

export type PlanListRow = {
  id: string;
  name: string;
  plan_type: string;
  price_amount: string;
  currency: string;
  is_active: boolean;
};

export type PlanDetail = PlanListRow & {
  description: string | null;
  duration_seconds: number | null;
  data_bytes_quota: number | null;
  bandwidth_up_kbps: number | null;
  bandwidth_down_kbps: number | null;
  status: string;
  router_ids: string[];
};

export type PaymentListRow = {
  id: string;
  order_reference: string;
  provider: string;
  amount: string;
  currency: string;
  payment_status: string;
};

export type PaymentDetail = PaymentListRow & {
  provider_ref: string | null;
  customer_id: string | null;
  plan_id: string | null;
  site_id: string | null;
  metadata: unknown;
  created_at: string;
  updated_at: string;
};

export type PaymentEventRow = {
  id: string;
  event_type: string;
  payload: unknown;
  created_at: string;
};

export type VoucherListRow = {
  id: string;
  code: string;
  status: string;
  plan_id: string;
  expires_at: string | null;
};

export type VoucherBatchListRow = { id: string; name: string; quantity: number; plan_id: string };

export type VoucherBatchDetail = {
  id: string;
  name: string;
  plan_id: string;
  quantity: number;
  prefix: string | null;
  requires_pin: boolean;
  status: string;
  voucher_total: number;
  vouchers_by_status: Record<string, number>;
  created_at: string;
};

export type SessionListRow = {
  id: string;
  router_id: string;
  mac_address: string;
  username: string | null;
  login_at: string;
  expires_at: string | null;
  status: string;
  bytes_up: number;
  bytes_down: number;
};

export type SiteRow = {
  id: string;
  name: string;
  slug: string;
  address: string | null;
  timezone: string;
  status: string;
};

export type SystemSettingRow = {
  key: string;
  value: Record<string, unknown> | null;
  description: string | null;
};

export type PortalPlan = {
  id: string;
  name: string;
  description: string | null;
  plan_type: string;
  price_amount: string;
  currency: string;
};

export type PortalBrandingResponse = {
  site: { id: string; name: string; slug: string };
  branding: {
    logo_url: string | null;
    primary_color: string | null;
    welcome_message: string | null;
    support_phone: string | null;
    extra: unknown;
  } | null;
};

export type PortalGrantSummary = {
  grant_id: string;
  plan_id: string;
  plan_name: string | null;
  source: string;
  entitlement: Record<string, unknown>;
};

export type PortalAccessStatus = {
  site: { id: string; name: string; slug: string } | null;
  customer_id: string | null;
  resolved_by?: string | null;
  has_usable_access: boolean;
  primary_access: PortalGrantSummary | null;
  usable_grants: PortalGrantSummary[];
  authorization?: {
    available: boolean;
    mode?: string;
    router_id?: string;
    router_name?: string;
    mac_address?: string;
    username?: string;
    password?: string;
    profile_name?: string;
    rate_limit?: string | null;
    limit_uptime_seconds?: number | null;
    login_url?: string | null;
    server_name?: string | null;
    destination?: string | null;
    nas?: Record<string, unknown>;
    reason?: string;
  } | null;
};

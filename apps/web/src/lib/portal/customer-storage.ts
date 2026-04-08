const KEY = (slug: string) => `esn_portal_customer_${slug}`;
const PHONE_KEY = (slug: string) => `esn_portal_phone_${slug}`;

export function getStoredCustomerId(siteSlug: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY(siteSlug));
}

export function setStoredCustomerId(siteSlug: string, customerId: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY(siteSlug), customerId.trim());
}

export function clearStoredCustomerId(siteSlug: string) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY(siteSlug));
}

export function getStoredPortalPhone(siteSlug: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(PHONE_KEY(siteSlug));
}

export function setStoredPortalPhone(siteSlug: string, phone: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PHONE_KEY(siteSlug), phone.trim());
}

export function clearStoredPortalPhone(siteSlug: string) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(PHONE_KEY(siteSlug));
}

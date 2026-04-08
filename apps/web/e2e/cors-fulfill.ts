import type { Route } from "@playwright/test";

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
};

export async function handleCorsPreflight(route: Route): Promise<boolean> {
  if (route.request().method() === "OPTIONS") {
    await route.fulfill({ status: 204, headers: CORS_HEADERS });
    return true;
  }
  return false;
}

export async function fulfillApiJson(route: Route, envelope: object) {
  await route.fulfill({
    status: 200,
    headers: CORS_HEADERS,
    contentType: "application/json",
    body: JSON.stringify(envelope),
  });
}

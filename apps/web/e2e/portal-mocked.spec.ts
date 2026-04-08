import { test, expect } from "@playwright/test";
import { installE2eBackendMocks } from "./mock-backend";

test.beforeEach(async ({ page }) => {
  await installE2eBackendMocks(page);
});

test.describe("Captive portal (mocked API)", () => {
  test("landing loads network summary", async ({ page }) => {
    await page.goto("/demo-site");
    await expect(page.getByRole("navigation", { name: /portal navigation/i })).toBeVisible();
    await expect(page.getByText(/2 of 2 online/i)).toBeVisible();
  });

  test("plans list shows mocked plan card", async ({ page }) => {
    await page.goto("/demo-site/plans");
    await expect(page.getByRole("heading", { name: /choose a plan/i })).toBeVisible();
    await expect(page.getByText("1 Hour")).toBeVisible();
    await expect(page.getByRole("link", { name: /continue to pay/i })).toBeVisible();
  });

  test("redeem page shows voucher form", async ({ page }) => {
    await page.goto("/demo-site/redeem");
    await expect(page.getByRole("heading", { name: /redeem voucher/i })).toBeVisible();
    await expect(page.getByLabel(/^Code/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /apply voucher/i })).toBeVisible();
  });

  test("access status can load with mocked API", async ({ page }) => {
    await page.goto("/demo-site/access");
    await page.getByLabel(/^Customer ID/i).fill("550e8400-e29b-41d4-a716-446655440000");
    await page.getByRole("button", { name: /check status/i }).click();
    await expect(page.getByText(/current plan/i)).toBeVisible();
    await expect(page.getByText("1 Hour")).toBeVisible();
  });
});

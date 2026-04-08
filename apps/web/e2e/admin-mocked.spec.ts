import { test, expect } from "@playwright/test";
import { installE2eBackendMocks } from "./mock-backend";

test.describe("Admin lists (mocked API)", () => {
  test.beforeEach(async ({ page }) => {
    await installE2eBackendMocks(page);
  });

  test("routers list shows mocked row when cookie present", async ({ page, context }) => {
    await context.addCookies([
      {
        name: "esn_at",
        value: "mock-token",
        url: "http://127.0.0.1:3000",
      },
    ]);
    await page.goto("/dashboard/routers");
    await expect(page.getByText("Router A")).toBeVisible();
    await expect(page.getByRole("link", { name: /view/i }).first()).toBeVisible();
  });

  test("customers list shows mocked row", async ({ page, context }) => {
    await context.addCookies([{ name: "esn_at", value: "mock-token", url: "http://127.0.0.1:3000" }]);
    await page.goto("/dashboard/customers");
    await expect(page.getByText("Test User")).toBeVisible();
  });

  test("plans list shows mocked plan", async ({ page, context }) => {
    await context.addCookies([{ name: "esn_at", value: "mock-token", url: "http://127.0.0.1:3000" }]);
    await page.goto("/dashboard/plans");
    await expect(page.getByText("Day pass")).toBeVisible();
  });
});

test.describe("Payment detail (mocked API)", () => {
  test.beforeEach(async ({ page }) => {
    await installE2eBackendMocks(page, { paymentId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" });
  });

  test("payment detail shows event timeline rows", async ({ page, context }) => {
    const paymentId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    await context.addCookies([{ name: "esn_at", value: "mock-token", url: "http://127.0.0.1:3000" }]);
    await page.goto(`/dashboard/payments/${paymentId}`);
    await expect(page.getByRole("heading", { name: "Event timeline" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "When" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "payment.created" })).toBeVisible();
  });
});

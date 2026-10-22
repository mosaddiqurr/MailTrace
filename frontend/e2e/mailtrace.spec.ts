import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("pasted headers produce an evidence-led report", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Paste headers" }).click();
  await page.getByLabel("Raw email headers").fill(
    "From: Alice <alice@example.com>\r\nTo: Bob <bob@example.net>\r\nSubject: Playwright evidence\r\nMessage-ID: <one@example.com>\r\n\r\n",
  );
  await page.getByRole("button", { name: "Analyse email" }).click();
  await expect(page.getByRole("heading", { name: "Playwright evidence" })).toBeVisible();
  await expect(page.getByText("Authentication evidence")).toBeVisible();
  await expect(page.getByText("Processed locally")).toHaveCount(0);
});

test("mobile navigation remains usable", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile");
  await page.goto("/");
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("link", { name: "Methodology", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Evidence before conclusions." })).toBeVisible();
});

test("suspicious eml upload shows supporting evidence", async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles(
    "../mailtrace/fixtures/spf-fail-reply-to.eml",
  );
  await page.getByRole("button", { name: "Analyse email" }).click();
  await expect(page.getByRole("heading", { name: "Account confirmation required" })).toBeVisible();
  await expect(page.getByText("Recorded SPF result: fail")).toBeVisible();
  await expect(page.getByText("Authentication evidence")).toBeVisible();
});

test("history persists after reload and supports deletion", async ({ page }, testInfo) => {
  const subject = `Persistent ${testInfo.project.name} ${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Paste headers" }).click();
  await page.getByLabel("Raw email headers").fill(
    `From: Persistence <persist@example.com>\r\nSubject: ${subject}\r\nMessage-ID: <persist@example.com>\r\n\r\n`,
  );
  await page.getByRole("button", { name: "Analyse email" }).click();
  await expect(page.getByRole("heading", { name: subject })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: subject })).toBeVisible();
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  }
  await page.getByRole("link", { name: "History", exact: true }).click();
  await expect(page.getByText(subject, { exact: true })).toBeVisible();
  page.on("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: `Delete ${subject}` }).click();
  await expect(page.getByText(subject, { exact: true })).toHaveCount(0);
});

test("local settings persist without enabling remote content", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("Retention period").selectOption("30");
  const checkbox = page.getByRole("checkbox");
  if (!(await checkbox.isChecked())) await page.locator("label.toggle").click();
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText("Settings saved locally.")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Retention period")).toHaveValue("30");
  await expect(page.getByRole("checkbox")).toBeChecked();
});

test("empty input cannot start an analysis", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Analyse email" })).toBeDisabled();
  await page.getByRole("button", { name: "Paste headers" }).click();
  await expect(page.getByRole("button", { name: "Analyse email" })).toBeDisabled();
});

test("analyse screen has no serious or critical axe violations", async ({ page }) => {
  await page.goto("/");
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const material = result.violations.filter(
    violation => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(material).toEqual([]);
});

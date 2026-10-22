import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";

for(const preference of ["no-preference","reduce"] as const) {
  test(`email sculpture animates continuously with ${preference}`, async ({ page }) => {
    await page.emulateMedia({reducedMotion:preference});
    await page.goto("/");
    const canvas = page.locator("canvas.email-signal-canvas");
    await expect(canvas).toBeVisible();
    const image = await canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL());
    await expect.poll(()=>canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL())).not.toBe(image);
    expect(page.workers()).toHaveLength(1);
    await expect(page.getByRole("button",{name:/sample|background animation/i})).toHaveCount(0);
    await expect(page.locator(".assurance-strip,.hero-bottom,.local-status,video")).toHaveCount(0);
  });
}

test("email sculpture stays animated without OffscreenCanvas support", async({page})=>{
  await page.addInitScript(()=>Object.defineProperty(HTMLCanvasElement.prototype,"transferControlToOffscreen",{value:undefined}));
  await page.goto("/");
  const canvas=page.locator("canvas.email-signal-canvas");
  const image=await canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL());
  await expect.poll(()=>canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL())).not.toBe(image);
  expect(page.workers()).toHaveLength(0);
});

test("off-screen animation releases the main thread and resumes when visible", async ({ page }) => {
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.goto("/");
  await page.getByRole("button",{name:"Paste headers",exact:true}).click();
  const field=page.getByLabel("Raw email headers");
  await field.evaluate(element=>element.scrollIntoView({block:"start",behavior:"instant"}));
  const canvas=page.locator("canvas.email-signal-canvas");
  await expect.poll(()=>canvas.evaluate(c=>c.getBoundingClientRect().bottom)).toBeLessThanOrEqual(80);
  await page.waitForTimeout(100);
  const still=await canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL());
  await field.pressSequentially("From: analyst@example.test\nSubject: Responsiveness",{delay:5,timeout:5000});
  await expect(field).toHaveValue("From: analyst@example.test\nSubject: Responsiveness");
  expect(await canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL())).toBe(still);
  await page.locator(".signal-hero").scrollIntoViewIfNeeded();
  await expect.poll(()=>canvas.evaluate((c:HTMLCanvasElement)=>c.toDataURL())).not.toBe(still);
});

test("redesigned screens stay accessible and fit the viewport", async ({ page }, testInfo) => {
  const output = "../.tmp/ui-review";
  await mkdir(output,{recursive:true});
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.goto("/");
  await page.screenshot({path:`${output}/${testInfo.project.name}-home.png`});
  await page.locator('input[type="file"]').setInputFiles("../mailtrace/fixtures/aligned-business.eml");
  await expect(page.getByText("aligned-business.eml")).toBeVisible();
  await page.locator("#evidence").screenshot({path:`${output}/${testInfo.project.name}-workspace.png`});
  await page.getByRole("button",{name:"Analyse email"}).click();
  await expect(page.getByRole("heading",{name:"Invoice status update"})).toBeVisible();
  await expect.poll(()=>page.workers().length).toBe(0);
  for (const [name,path] of [["report",null],["history","/history"],["methodology","/methodology"],["settings","/settings"]] as const) {
    if(path) {
      if(testInfo.project.name==="mobile") await page.getByRole("button",{name:"Toggle navigation"}).click();
      const label = name[0].toUpperCase()+name.slice(1);
      await page.getByRole("navigation",{name:"Primary navigation"}).getByRole("link",{name:label,exact:true}).click();
    }
    if(name==="history") await expect(page.getByText("Invoice status update").first()).toBeVisible();
    if(name==="settings") await expect(page.getByLabel("Retention period")).toBeVisible();
    const result = await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa"]).analyze();
    expect(result.violations.filter(v=>v.impact==="serious"||v.impact==="critical"),`${name} accessibility`).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name} horizontal overflow`).toBe(true);
    await page.screenshot({path:`${output}/${testInfo.project.name}-${name}.png`,fullPage:true});
    if(name==="report") {
      await page.getByText("Export report",{exact:true}).click();
      await expect(page.getByRole("link",{name:"PDF",exact:true})).toBeVisible();
    }
  }
});

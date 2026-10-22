import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import globalSetup from "../e2e/global-setup.ts";

// The same isolated server/data lifecycle as E2E keeps private local history out of documentation.
const stopServer=await globalSetup();
let browser;
const output=new URL("../../docs/screenshots/",import.meta.url);
const fixture=name=>fileURLToPath(new URL(`../../mailtrace/fixtures/${name}`,import.meta.url));
try {
  await mkdir(output,{recursive:true});
  browser=await chromium.launch();
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1,reducedMotion:"reduce"});
  const capture=async name=>{
    await page.evaluate(()=>document.fonts.ready);
    await page.screenshot({path:fileURLToPath(new URL(name,output))});
  };
  const upload=async(filename,subject)=>{
    await page.goto("http://127.0.0.1:8000/");
    await page.locator('input[type="file"]').setInputFiles(fixture(filename));
    await page.getByRole("button",{name:"Analyse email",exact:true}).click();
    await page.getByRole("heading",{name:subject,exact:true}).waitFor();
  };
  const section=async id=>page.locator(`#${id}`).evaluate(element=>element.scrollIntoView({block:"start",behavior:"instant"}));

  await page.goto("http://127.0.0.1:8000/");
  await page.waitForFunction(()=>document.querySelector("canvas")?.toDataURL().length>8000);
  await capture("00-landing.png");
  await section("evidence");
  await capture("01-analysis-input.png");
  await upload("aligned-business.eml","Invoice status update");
  await upload("spf-fail-reply-to.eml","Account confirmation required");
  await capture("02-investigation-overview.png");
  await section("authentication");
  await capture("03-authentication-analysis.png");
  await section("delivery");
  await capture("04-delivery-path.png");
  await upload("double-extension.eml","Double extension");
  await section("content");
  await capture("05-urls-attachments.png");
  await page.getByRole("navigation",{name:"Primary navigation"}).getByRole("link",{name:"History",exact:true}).click();
  await page.getByText("Account confirmation required",{exact:true}).waitFor();
  await capture("06-report-or-history.png");
  console.log("Captured seven current application screenshots using isolated synthetic evidence.");
} finally {
  try { await browser?.close(); }
  finally { await stopServer(); }
}

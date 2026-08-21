import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("encodes uploads, headers, settings, reads, and deletions", async () => {
  const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({id:"a1",preferences:{}}), {
    status: 200, headers: {"Content-Type":"application/json"},
  })));
  vi.stubGlobal("fetch", fetchMock);
  await api.upload(new File(["mail"], "mail.eml"));
  await api.headers("From: a@example.com");
  await api.list();
  await api.get("a1");
  await api.settings();
  await api.saveSettings({retention_days:7,dns_enrichment_enabled:false});
  expect(fetchMock).toHaveBeenCalledTimes(6);
});

it("handles no-content responses and safe errors", async () => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(null, {status:204}))));
  await expect(api.remove("a1")).resolves.toBeUndefined();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({detail:"Safe failure"}), {
    status: 422, headers: {"Content-Type":"application/json"},
  }))));
  await expect(api.get("bad")).rejects.toThrow("Safe failure");
});

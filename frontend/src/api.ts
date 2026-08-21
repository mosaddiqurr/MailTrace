export type Address = { display_name?: string; address?: string; domain?: string };
export type Observation = {
  rule_id: string; title: string; severity: string; confidence: string;
  description: string; explanation?: string; evidence_reference?: string[];
  supporting_headers?: string[]; why_it_matters?: string; why_matters?: string;
  limitation?: string; analyst_action?: string; recommended_action?: string;
};
export type Analysis = {
  id: string; case_id: string; status: string; stage: string; created_at: string;
  title: string; filename: string; sha256: string; file_size: number; input_type: string;
  summary: {
    subject?: string; date?: string; from: Address[]; assessment: {
      label: string; risk: string; confidence: string; basis: string[]; observation_count: number;
    }; authentication: Record<string, unknown>; hop_count: number;
    attachment_count: number; observation_count: number;
  };
  parsed_message: Record<string, unknown>; authentication: Record<string, any>;
  hops: Array<Record<string, any>>; observations: Observation[];
  attachments: Array<Record<string, any>>; mime_structure: Record<string, any>;
  urls: Array<Record<string, any>>; limitations: string[]; warnings: Array<Record<string, any>>;
  timings: Record<string, number>; raw_available: boolean; exports: string[];
};
export type Preferences = { retention_days: 7 | 30 | 90 | null; dns_enrichment_enabled: boolean };

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "MailTrace could not complete the request." }));
    throw new Error(body.detail || "MailTrace could not complete the request.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  list: () => request<Analysis[]>("/api/analyses"),
  get: (id: string) => request<Analysis>(`/api/analyses/${id}`),
  remove: (id: string) => request<void>(`/api/analyses/${id}`, { method: "DELETE" }),
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("retain_original", "true");
    return request<{id: string}>("/api/analyses/upload", { method: "POST", body: form });
  },
  headers: (raw_headers: string) => request<{id: string}>("/api/analyses/headers", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_headers, filename: "pasted-headers.txt", retain_original: true }),
  }),
  settings: () => request<{preferences: Preferences; limits: Record<string, number>}>("/api/settings"),
  saveSettings: (value: Preferences) => request<Preferences>("/api/settings", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value),
  }),
};

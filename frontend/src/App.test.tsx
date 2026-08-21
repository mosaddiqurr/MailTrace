import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const analysis = {
  id: "a1", case_id: "c1", status: "complete", stage: "building_report",
  created_at: "2026-07-23T00:00:00Z", title: "Quarterly report",
  filename: "message.eml", sha256: "a".repeat(64), file_size: 1024, input_type: "eml",
  summary: {
    subject: "Quarterly report", date: "Wed, 23 Jul 2026 09:00:00 +0000",
    from: [{display_name:"Alice",address:"alice@example.com",domain:"example.com"}],
    assessment: {label:"Some evidence needs review",risk:"medium",confidence:"high",basis:["One observation was evaluated."],observation_count:1},
    authentication:{},hop_count:1,attachment_count:1,observation_count:1,
  },
  parsed_message: {content_type:"multipart/mixed",headers:[],from:[{address:"alice@example.com",domain:"example.com"}]},
  authentication: {
    spf:{result:"pass",domain:"example.com",raw:"spf=pass"},
    dkim:{result:"pass",domain:"example.com",raw:"dkim=pass"},
    dmarc:{result:"pass",domain:"example.com",raw:"dmarc=pass"},
    alignment:{spf_aligned:true,dkim_aligned:true},
    arc:{chain_instances:[1]},
  },
  hops:[{from_host:"mail.example.com",by_host:"mx.example.net",utc_time:"2026-07-23T09:00:00Z",raw:"Received: ..."}],
  observations:[{rule_id:"ID-001",title:"Reply destination differs",severity:"medium",confidence:"high",description:"Reply-To differs.",supporting_headers:["From","Reply-To"],why_matters:"Replies go elsewhere.",limitation:"May be legitimate.",recommended_action:"Verify the sender."}],
  attachments:[{filename:"invoice.pdf",content_type:"application/pdf",size:120,sha256:"b".repeat(64)}],
  mime_structure:{available:true,part_count:3,html_available:true,plain_text_preview:"Hello"},
  urls:[{url:"https://example.com",source:"text/plain",fetched:false}],
  limitations:["Authentication was not independently verified."],warnings:[],timings:{total_ms:12},
  raw_available:true,exports:["pdf","json","csv","txt","html","bundle"],
};

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(status === 204 ? null : JSON.stringify(value), {
    status, headers: {"Content-Type":"application/json"},
  }));
}

function renderAt(path: string) {
  const client = new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App/></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/analyses") return json([analysis]);
    if (url === "/api/analyses/a1") return json(analysis);
    if (url === "/api/analyses/headers") return json({id:"a1"}, 202);
    if (url === "/api/settings" && init?.method === "PUT") return json({retention_days:30,dns_enrichment_enabled:true});
    if (url === "/api/settings") return json({preferences:{retention_days:null,dns_enrichment_enabled:false},limits:{max_upload_bytes:10485760}});
    if (url === "/api/analyses/a1" && init?.method === "DELETE") return json(null, 204);
    return json({detail:"Not found"}, 404);
  }));
  vi.stubGlobal("confirm", vi.fn(() => true));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MailTrace application", () => {
  it("uses the MailTrace logo in the application header", () => {
    renderAt("/");
    const logo = document.querySelector<HTMLImageElement>(".brand-logo");
    expect(logo).toHaveAttribute("src", "/logo.png");
    expect(screen.getByRole("link", {name:"MailTrace home"})).toContainElement(logo);
  });

  it("submits pasted headers through the real workflow", async () => {
    const user = userEvent.setup();
    renderAt("/");
    await user.click(screen.getByRole("button",{name:"Paste headers"}));
    await user.type(screen.getByLabelText("Raw email headers"), "From: alice@example.com\nSubject: Test");
    await user.click(screen.getByRole("button",{name:"Analyse email"}));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/analyses/headers", expect.objectContaining({method:"POST"})));
  });

  it("uploads an eml file and rejects unsupported filenames", async () => {
    const user = userEvent.setup();
    renderAt("/");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["From: a@example.com\r\n\r\n"], "mail.eml", {type:"message/rfc822"}));
    expect(screen.getByText("mail.eml")).toBeInTheDocument();
    await user.click(screen.getByRole("button",{name:"Analyse email"}));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/analyses/upload", expect.objectContaining({method:"POST"})));
    await user.upload(input, new File(["bad"], "mail.exe"));
    expect(screen.queryByText("mail.exe")).not.toBeInTheDocument();
  });

  it("supports keyboard and drag interactions", async () => {
    const user = userEvent.setup();
    renderAt("/");
    const zone = screen.getByRole("button",{name:/Drop an .eml file here/});
    fireEvent.dragOver(zone);
    expect(zone).toHaveClass("drag");
    fireEvent.dragLeave(zone);
    expect(zone).not.toHaveClass("drag");
    fireEvent.keyDown(zone,{key:"Enter"});
    await user.click(screen.getByRole("button",{name:"Paste headers"}));
    await user.click(screen.getByRole("button",{name:"Upload .eml"}));
    expect(screen.getByText("Drop an .eml file here")).toBeInTheDocument();
  });

  it("renders the evidence-led report", async () => {
    renderAt("/analysis/a1");
    expect(await screen.findByRole("heading",{name:"Quarterly report"})).toBeInTheDocument();
    expect(screen.getAllByText("Some evidence needs review").length).toBeGreaterThan(0);
    expect(screen.getByText("Reply destination differs")).toBeInTheDocument();
    expect(screen.getByText("Authentication evidence")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Raw Received evidence"));
    expect(screen.getByText("Received: ...")).toBeInTheDocument();
  });

  it("lists and deletes local history", async () => {
    const user = userEvent.setup();
    renderAt("/history");
    expect(await screen.findByText("message.eml · 7/23/2026, 8:00:00 AM")).toBeInTheDocument();
    await user.click(screen.getByRole("button",{name:"Delete Quarterly report"}));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/analyses/a1", {method:"DELETE"}));
  });

  it("filters history and exposes the mobile navigation", async () => {
    const user = userEvent.setup();
    renderAt("/history");
    await screen.findByText("Quarterly report");
    await user.type(screen.getByLabelText("Search analyses"), "missing");
    expect(screen.getByText("No analyses found")).toBeInTheDocument();
    await user.click(screen.getByRole("button",{name:"Toggle navigation"}));
    expect(screen.getByRole("navigation")).toHaveClass("open");
  });

  it("shows safe API errors", async () => {
    vi.mocked(fetch).mockImplementationOnce(() => json({detail:"Analysis not found"}, 404));
    renderAt("/analysis/missing");
    expect(await screen.findByRole("alert")).toHaveTextContent("Analysis not found");
  });

  it("renders unavailable evidence without inventing findings", async () => {
    const limited = {
      ...analysis,
      id:"a2",
      summary:{...analysis.summary,subject:undefined,from:[],assessment:{...analysis.summary.assessment,label:"Insufficient evidence",risk:"unknown"},hop_count:0,attachment_count:0,observation_count:0},
      observations:[],hops:[],attachments:[],urls:[],raw_available:false,
      mime_structure:{available:false},
      parsed_message:{},
    };
    vi.mocked(fetch).mockImplementationOnce(() => json(limited));
    renderAt("/analysis/a2");
    expect(await screen.findByRole("heading",{name:"Untitled email"})).toBeInTheDocument();
    expect(screen.getByText("No material observations")).toBeInTheDocument();
    expect(screen.getByText("No delivery hops available")).toBeInTheDocument();
    expect(screen.getByText("No attachments were inventoried.")).toBeInTheDocument();
  });

  it("explains methodology", () => {
    renderAt("/methodology");
    expect(screen.getByRole("heading",{name:"Evidence before conclusions."})).toBeInTheDocument();
    expect(screen.getByText("Reported authentication")).toBeInTheDocument();
  });

  it("persists local settings", async () => {
    const user = userEvent.setup();
    renderAt("/settings");
    const select = await screen.findByLabelText("Retention period");
    await user.selectOptions(select, "30");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button",{name:"Save settings"}));
    expect(await screen.findByText("Settings saved locally.")).toBeInTheDocument();
  });
});

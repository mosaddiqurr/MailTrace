import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, Clock3, Code2, Download,
  FileCheck2, FileSearch, FileText, Fingerprint, HardDrive, History as HistoryIcon, Info, LockKeyhole, Mail, Menu,
  Network, Paperclip, Plus, Search, Settings as SettingsIcon, ShieldCheck, Trash2, UploadCloud, X,
} from "lucide-react";
import { api, type Observation, type Preferences } from "./api";
import SignalHero from "./SignalHero";
import Capabilities from "./Capabilities";

const nav = [
  ["/", "Analyse", FileSearch],
  ["/history", "History", HistoryIcon],
  ["/methodology", "Methodology", FileText],
  ["/settings", "Settings", SettingsIcon],
] as const;

function Layout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const menuButton = useRef<HTMLButtonElement>(null);
  const header = useRef<HTMLElement>(null);
  useEffect(() => {
    window.scrollTo?.({ top: 0, behavior: "instant" });
  }, [location.pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); menuButton.current?.focus(); }
    };
    const outside = (event: PointerEvent) => {
      if (!header.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", outside);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("pointerdown", outside); };
  }, [open]);
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header ref={header} className={`topbar ${location.pathname === "/" ? "topbar-home" : ""}`}>
      <NavLink to="/" className="brand" aria-label="MailTrace home">
        <span className="brand-logo-frame" aria-hidden="true">
          <img className="brand-logo" src="/logo-72.webp" srcSet="/logo-144.webp 2x" alt="" width="36" height="36" decoding="async" />
        </span>
        <span className="brand-wordmark">MailTrace<span className="brand-period">.</span></span>
      </NavLink>
      <button ref={menuButton} className="menu-button" aria-label="Toggle navigation" aria-expanded={open} aria-controls="primary-navigation" onClick={() => setOpen(!open)}>
        {open ? <X /> : <Menu />}
      </button>
      <nav id="primary-navigation" className={open ? "nav open" : "nav"} aria-label="Primary navigation">
        {nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/"}
          onClick={() => setOpen(false)}><Icon size={17}/>{label}</NavLink>)}
      </nav>
      <div className="header-right"><NavLink className="header-action" to="/" aria-label="New investigation" onClick={event => {if(location.pathname === "/") {event.preventDefault(); document.getElementById("evidence")?.scrollIntoView({behavior:window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});}}}><Plus size={15} />New investigation</NavLink></div>
    </header>
    <main id="main-content"><Routes>
      <Route path="/" element={<Analyse />} />
      <Route path="/analysis/:id" element={<Result />} />
      <Route path="/history" element={<History />} />
      <Route path="/methodology" element={<Methodology />} />
      <Route path="/settings" element={<Settings />} />
    </Routes></main>
    <footer className="site-footer"><div className="footer-inner"><div className="footer-brand"><img src="/logo-72.webp" width="28" height="28" alt="" loading="lazy" decoding="async" /><strong>MailTrace.</strong><span>Follow the evidence.</span></div><p>MailTrace analyses email evidence locally. It does not determine whether a message is safe.</p><span className="footer-lock"><LockKeyhole size={12} /> Your evidence stays yours.</span></div></footer>
  </div>;
}

export default function App() { return <Layout />; }

function Analyse() {
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"file"|"headers">("file");
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState("");
  const [drag, setDrag] = useState(false);
  const [validation, setValidation] = useState("");
  const submit = useMutation({
    mutationFn: () => mode === "file" && file ? api.upload(file) : api.headers(headers),
    onSuccess: ({id}) => navigate(`/analysis/${id}`),
  });
  const choose = (value?: File) => {
    if (!value) return;
    setValidation("");
    if (!value.name.toLowerCase().endsWith(".eml")) { setFile(null); setValidation("Choose an .eml email file to continue."); return; }
    if (value.size > 10 * 1024 * 1024) { setFile(null); setValidation("This file exceeds the 10 MiB limit. Choose a smaller .eml file."); return; }
    setFile(value);
  };
  return <>
    <SignalHero />
    <div className="page evidence-workspace" id="evidence">
    <div className="workspace-input">
    <section className="analysis-panel" aria-labelledby="evidence-heading">
      <div className="panel-heading">
        <div className="input-heading"><h2 id="evidence-heading">Add email evidence</h2><p>Upload a message or paste headers. Your original evidence stays unchanged.</p></div>
        <div className="mode-switch" role="group" aria-label="Input method">
          <button className={mode === "file" ? "active" : ""} aria-pressed={mode === "file"} onClick={() => {setMode("file"); setValidation("");}}><UploadCloud size={15}/>Upload .eml</button>
          <button className={mode === "headers" ? "active" : ""} aria-pressed={mode === "headers"} onClick={() => {setMode("headers"); setValidation("");}}><Code2 size={15}/>Paste headers</button>
        </div>
      </div>
      {mode === "file" ? <div
        className={`dropzone ${drag ? "drag" : ""}`} tabIndex={0} role="button"
        onKeyDown={(e) => {if (e.key === "Enter" || e.key === " ") {e.preventDefault(); input.current?.click();}}}
        onClick={() => input.current?.click()} onDragOver={(e) => {e.preventDefault(); setDrag(true);}}
        onDragLeave={() => setDrag(false)} onDrop={(e) => {e.preventDefault(); setDrag(false); choose(e.dataTransfer.files[0]);}}>
        <input ref={input} hidden type="file" accept=".eml,message/rfc822" onChange={(e) => choose(e.target.files?.[0])}/>
        <div className={`upload-icon ${file ? "file-selected" : ""}`}>{file ? <FileCheck2 size={29} strokeWidth={1.3}/> : <UploadCloud size={29} strokeWidth={1.3}/>}</div>
        {file ? <><strong>{file.name}</strong><span>{formatBytes(file.size)} · ready to analyse</span></>
          : <><strong>Drop an .eml file here</strong><span>or <em>browse files</em> on your device</span><small>.EML FORMAT <span/> UP TO 10 MiB</small></>}
      </div> : <div className="field">
        <label htmlFor="raw-headers">Raw email headers</label>
        <textarea id="raw-headers" value={headers} onChange={(e) => setHeaders(e.target.value)}
          placeholder={"From: sender@example.com\nTo: recipient@example.net\nSubject: Message subject\nReceived: ..."} />
        <small>Header folding and original order are preserved. Body, MIME, attachment, and link analysis will be unavailable.</small>
      </div>}
      {validation && <div className="error" role="alert"><AlertTriangle />{validation}</div>}
      {submit.error && <div className="error" role="alert"><AlertTriangle />{submit.error.message}</div>}
      <div className="panel-actions">
        <div className="privacy"><LockKeyhole/><span><strong>Processed locally</strong>No external service receives your email.</span></div>
        <button className="primary" disabled={submit.isPending || (mode === "file" ? !file : !headers.trim())}
          onClick={() => submit.mutate()}>{submit.isPending ? "Analysing evidence…" : "Analyse email"}<ArrowRight/></button>
      </div>
      {submit.isPending && <div className="progress" role="status" aria-live="polite">
        <span className="spinner"/> Validating evidence and building the forensic report…
      </div>}
    </section>
    <div className="safety-line"><ShieldCheck/><span><strong>Safe by design.</strong> Attachments are never executed, links are never followed, and remote images are never loaded.</span></div>
    </div>
  </div><Capabilities /></>;
}

function Result() {
  const {id = ""} = useParams();
  const result = useQuery({queryKey: ["analysis", id], queryFn: () => api.get(id)});
  if (result.isLoading) return <Loading />;
  if (result.error || !result.data) return <PageError message={result.error?.message || "Analysis not found."}/>;
  const a = result.data;
  const assessment = a.summary.assessment;
  const from = a.summary.from?.[0];
  const auth = a.authentication;
  return <div className="page report-page">
    <div className="report-head">
      <div>
        <NavLink to="/history" className="back-link"><ArrowLeft size={14}/> Analysis history</NavLink>
        <p className="eyebrow"><FileSearch size={13}/> FORENSIC REPORT</p>
        <h1>{a.summary.subject || "Untitled email"}</h1>
        <p>{from?.display_name || from?.address || "Sender unavailable"} · {a.filename}</p>
      </div>
      <details className="export-menu"><summary><Download size={16}/><span>Export report</span><ChevronDown size={14}/></summary>
        <div>{a.exports.map((format) => <a key={format} href={`/api/analyses/${a.id}/exports/${format}`}><FileText size={14}/>{format === "bundle" ? "Evidence bundle" : format.toUpperCase()}<ArrowRight size={13}/></a>)}</div>
      </details>
    </div>
    <section className={`assessment assessment-${assessment.risk}`}>
      <div className="assessment-icon">{assessment.risk === "low" ? <CheckCircle2/> : <AlertTriangle/>}</div>
      <div><span>ASSESSMENT</span><h2>{assessment.label}</h2>
        <p>{assessment.basis?.[0]} Review the evidence and limitations below before taking action.</p></div>
      <dl><div><dt>Risk</dt><dd>{assessment.risk}</dd></div><div><dt>Confidence</dt><dd>{assessment.confidence}</dd></div></dl>
    </section>
    <div className="report-metrics"><Metric icon={<Network/>} label="Delivery hops" value={String(a.summary.hop_count)}/><Metric icon={<Paperclip/>} label="Attachments" value={String(a.summary.attachment_count)}/><Metric icon={<Fingerprint/>} label="Observations" value={String(a.observations.length)}/><Metric icon={<HardDrive/>} label="Evidence size" value={formatBytes(a.file_size)}/></div>
    <div className="report-grid">
      <aside className="section-nav" aria-label="Report sections">
        <span className="section-nav-label">IN THIS REPORT</span>
        {([ ["summary", "Summary", FileSearch], ["observations", "Observations", Fingerprint], ["identity", "Identity", Mail], ["authentication", "Authentication", ShieldCheck], ["delivery", "Delivery", Network], ["content", "Content", Paperclip], ["technical", "Technical", Code2], ["limitations", "Limitations", Info] ] as const).map(([id,label,Icon]) =>
          <a key={id} href={`#${id}`}><Icon size={15}/>{label}</a>)}
        <div className="report-local-note"><LockKeyhole size={15}/><strong>Evidence stays local</strong><p>Preserved on this device. Never sent for external processing.</p></div>
      </aside>
      <article className="report-content">
        <ReportSection id="summary" title="Assessment summary">
          <div className="fact-grid">
            <Fact label="Displayed sender" value={from?.display_name || "Not present"} />
            <Fact label="Sender address" value={from?.address || "Not present"} mono />
            <Fact label="Message date" value={a.summary.date || "Not present"} />
            <Fact label="Evidence hash" value={a.sha256} mono />
            <Fact label="Delivery hops" value={String(a.summary.hop_count)} />
            <Fact label="Attachments" value={String(a.summary.attachment_count)} />
          </div>
        </ReportSection>
        <ReportSection id="observations" title="Why this assessment" count={a.observations.length}>
          {a.observations.length ? <div className="observation-list">{a.observations.map(o => <ObservationRow key={o.rule_id} item={o}/>)}</div>
            : <Empty icon={<CheckCircle2/>} title="No material observations" text="MailTrace found no clear concern in the available evidence. This is not a guarantee that the message is safe."/>}
        </ReportSection>
        <ReportSection id="identity" title="Sender identity">
          <IdentityTable parsed={a.parsed_message}/>
        </ReportSection>
        <ReportSection id="authentication" title="Authentication evidence">
          <p className="notice"><Info/>These are results reported inside the message. MailTrace did not independently verify the signatures or sending IP.</p>
          <div className="auth-grid">
            {["spf","dkim","dmarc"].map(key => <AuthItem key={key} name={key.toUpperCase()} value={auth[key] || {}} />)}
          </div>
          <KeyValues title="Alignment" value={auth.alignment || {}} />
          {auth.arc && <KeyValues title="ARC chain evidence" value={auth.arc}/>}
        </ReportSection>
        <ReportSection id="delivery" title="Delivery path" count={a.hops.length}>
          <p className="section-note">Shown in chronological sending order. Earlier headers may have been added before the message reached a trusted system.</p>
          {a.hops.length ? <ol className="route">{a.hops.map((hop, i) => <li key={i}>
            <span className="route-node">{i+1}</span><div><strong>{hop.from_host || "Unknown sender"}</strong><ArrowRight/>
            <strong>{hop.by_host || "Unknown receiver"}</strong><p>{hop.utc_time || hop.timestamp || "Timestamp unavailable"} {hop.with ? `· ${hop.with}` : ""}</p>
            <details><summary>Raw Received evidence</summary><pre>{hop.raw}</pre></details></div></li>)}</ol>
            : <Empty icon={<Network/>} title="No delivery hops available" text="No parseable Received headers were found."/>}
        </ReportSection>
        <ReportSection id="content" title="Message content and attachments">
          <div className="fact-grid">
            <Fact label="Content type" value={String(a.parsed_message.content_type || "Unknown")} />
            <Fact label="MIME parts" value={String(a.mime_structure.part_count ?? "Unavailable")} />
            <Fact label="HTML present" value={a.mime_structure.html_available ? "Yes (not rendered)" : "No"} />
            <Fact label="Extracted URLs" value={String(a.urls.length)} />
          </div>
          {a.mime_structure.plain_text_preview && <details><summary>Safe plain-text preview</summary><pre>{a.mime_structure.plain_text_preview}</pre></details>}
          <h3>Attachments</h3>
          {a.attachments.length ? <DataTable rows={a.attachments} columns={["filename","content_type","size","sha256"]}/> :
            <p className="muted">No attachments were inventoried.</p>}
          <h3>URLs</h3>
          {a.urls.length ? <DataTable rows={a.urls} columns={["url","source","fetched"]}/> :
            <p className="muted">No URLs were extracted from available content.</p>}
        </ReportSection>
        <ReportSection id="technical" title="Technical evidence">
          <details><summary>Raw parsed headers</summary><pre>{JSON.stringify(a.parsed_message.headers || [], null, 2)}</pre></details>
          <p className="hash"><strong>SHA-256</strong><code>{a.sha256}</code></p>
          {a.raw_available && <a className="secondary-button" href={`/api/analyses/${a.id}/raw`}><Download/>Download preserved evidence</a>}
        </ReportSection>
        <ReportSection id="limitations" title="Limitations">
          <ul className="limitations">{a.limitations.map((x,i)=><li key={i}>{x}</li>)}</ul>
          {a.warnings.length > 0 && <><h3>Parser warnings</h3><pre>{JSON.stringify(a.warnings, null, 2)}</pre></>}
        </ReportSection>
      </article>
    </div>
  </div>;
}

function History() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const analyses = useQuery({queryKey:["analyses"], queryFn: api.list});
  const remove = useMutation({mutationFn: api.remove, onSuccess: () => qc.invalidateQueries({queryKey:["analyses"]})});
  const records = analyses.data || [];
  const reviewCount = records.filter(x => ["medium","high"].includes(x.summary.assessment.risk)).length;
  const rows = records.filter(x => `${x.summary.subject || ""} ${x.title} ${x.filename}`.toLowerCase().includes(search.toLowerCase()) && (filter === "all" || (filter === "review" ? ["medium","high"].includes(x.summary.assessment.risk) : x.summary.assessment.risk === "low")));
  return <div className="page history-page"><div className="page-title-row"><div><p className="eyebrow"><HistoryIcon size={13}/> LOCAL RECORDS</p><h1>Analysis history</h1><p>Every investigation, in one place. Pick up where you left off.</p></div><NavLink className="primary" to="/"><Plus size={16}/>New analysis</NavLink></div>
    <div className="history-metrics"><Metric icon={<FileSearch/>} label="Retained analyses" value={analyses.isLoading ? "..." : String(records.length)}/><Metric icon={<Fingerprint/>} label="Need review" value={analyses.isLoading ? "..." : String(reviewCount)}/><Metric icon={<HardDrive/>} label="Evidence retained" value={analyses.isLoading ? "..." : formatBytes(records.reduce((sum,x) => sum + (x.raw_available ? x.file_size : 0),0))}/></div>
    <div className="history-controls"><div className="history-filters" role="group" aria-label="Filter analyses">{[["all","All reports"],["review","Needs review"],["low","Low concern"]].map(([value,label])=><button key={value} aria-pressed={filter===value} className={filter===value?"active":""} onClick={()=>setFilter(value)}>{label}</button>)}</div><div className="search"><Search/><input aria-label="Search analyses" placeholder="Search subject or filename" value={search} onChange={e=>setSearch(e.target.value)}/>{search && <button className="icon-button" aria-label="Clear search" onClick={()=>setSearch("")}><X size={14}/></button>}</div></div>
    {remove.error && <div className="error" role="alert"><AlertTriangle/>{remove.error.message}</div>}
    {analyses.error ? <PageError message={analyses.error.message}/> : analyses.isLoading ? <Loading/> : rows.length ? <div className="history-table">
      <div className="history-table-heading"><span>Evidence / subject</span><span>Assessment</span><span>Findings</span><span/></div>
      {rows.map(a => <div className="history-row" key={a.id}>
        <div className={`history-file-icon ${a.summary.assessment.risk}`}><Mail size={19}/></div>
        <NavLink to={`/analysis/${a.id}`}><strong>{a.summary.subject || "Untitled email"}</strong><span>{a.filename} · {new Date(a.created_at).toLocaleString()}</span></NavLink>
        <span className={`assessment-text ${a.summary.assessment.risk}`}>{a.summary.assessment.label}</span>
        <span>{a.summary.observation_count} observations</span>
        <button className="icon-button" disabled={remove.isPending} aria-label={`Delete ${a.title}`} onClick={()=>confirm("Permanently delete this local analysis and retained evidence?") && remove.mutate(a.id)}><Trash2/></button>
      </div>)}</div> : <Empty icon={<Clock3/>} title="No analyses found" text="Analyse an .eml file or paste raw headers to create your first report."/>}
    <p className="records-note"><LockKeyhole size={13}/> Reports and retained evidence are stored on this device. <NavLink to="/settings">Manage retention <ArrowRight size={12}/></NavLink></p>
  </div>;
}

function Methodology() {
  return <div className="page reading methodology-page"><div className="reading-intro"><span className="section-symbol"><Fingerprint size={23}/></span><p className="eyebrow">HOW MAILTRACE WORKS</p><h1>Evidence before conclusions.</h1>
    <p className="lead">MailTrace separates facts found in the message from reported authentication results, derived comparisons, and heuristic observations.</p></div>
    <div className="method-steps">{([
      [FileText,"Direct evidence","Headers, MIME structure, filenames, hashes, URLs, and timestamps are preserved or derived directly from the supplied bytes."],
      [ShieldCheck,"Reported authentication","SPF, DKIM, DMARC, and ARC values are claims recorded by receiving systems. They are not fresh cryptographic verification."],
      [Network,"Derived comparisons","Identity and authentication domains are compared to explain alignment without treating every mismatch as malicious."],
      [Fingerprint,"Contextual observations","Related signals are grouped, assigned severity and confidence, and paired with evidence, limitations, and a next action."],
    ] as const).map(([Icon,t,x])=><div key={t}><span><Icon size={21} strokeWidth={1.5}/></span><div><h2>{t}</h2><p>{x}</p></div></div>)}</div>
    <section><h2>Assessment language</h2><p>Risk describes the seriousness of observed evidence. Confidence describes how strongly the available evidence supports the interpretation. MailTrace never labels a message “guaranteed safe” or “definitely malicious.”</p></section>
    <section><h2>Trust boundaries</h2><p>Received and Authentication-Results headers become more useful when they can be associated with a trusted receiving system. Earlier headers can be forged. Live DNS enrichment, when explicitly enabled, reflects current records and cannot recreate historical DNS state.</p></section><NavLink className="primary" to="/">Start an investigation <ArrowRight size={16}/></NavLink>
  </div>;
}

function Settings() {
  const qc = useQueryClient();
  const query = useQuery({queryKey:["settings"], queryFn: api.settings});
  const [draft, setDraft] = useState<Preferences | null>(null);
  const save = useMutation({mutationFn: api.saveSettings, onSuccess: (x)=>{setDraft(x); qc.invalidateQueries({queryKey:["settings"]});}});
  if (query.isLoading) return <Loading/>;
  if (query.error) return <PageError message={query.error.message}/>;
  const value = draft || query.data?.preferences || {retention_days:null,dns_enrichment_enabled:false};
  return <div className="page reading settings-page"><p className="eyebrow"><SettingsIcon size={13}/> LOCAL CONTROLS</p><h1>Your workspace. Your rules.</h1><p className="lead">Control how long MailTrace keeps evidence and whether optional current-DNS lookups are available.</p>
    <div className="settings-panel"><div className="settings-panel-title"><SettingsIcon size={18}/><h2>Settings</h2></div>
    <section className="settings-section"><div className="settings-section-copy"><span className="settings-icon"><HardDrive size={20}/></span><div><h2>Evidence retention</h2><p>Deleting an analysis always removes its retained original and report data.</p></div></div>
      <label>Retention period<select value={value.retention_days ?? ""} onChange={e=>setDraft({...value,retention_days:e.target.value ? Number(e.target.value) as 7|30|90:null})}>
        <option value="">Keep until I delete it</option><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option>
      </select></label></section>
    <section className="settings-section"><div className="settings-section-copy"><span className="settings-icon"><Network size={20}/></span><div><h2 id="dns-label">Optional DNS enrichment</h2><p id="dns-description">Allow explicit current DNS lookups. This does not independently verify historical authentication.</p></div></div>
      <label className="toggle"><input aria-labelledby="dns-label" aria-describedby="dns-description" type="checkbox" checked={value.dns_enrichment_enabled} onChange={e=>setDraft({...value,dns_enrichment_enabled:e.target.checked})}/><span/></label></section>
    <div className="settings-actions"><span><LockKeyhole size={14}/> Changes are saved on this device.</span><button className="primary" onClick={()=>save.mutate(value)} disabled={save.isPending}>{save.isPending?"Saving…":"Save settings"}<ArrowRight size={15}/></button></div></div>
    {save.isSuccess && <p role="status" className="saved"><CheckCircle2/>Settings saved locally.</p>}
    {save.error && <div className="error" role="alert"><AlertTriangle/>{save.error.message}</div>}
    <div className="settings-privacy"><ShieldCheck size={22}/><div><h2>Private by design.</h2><p>Message content stays local. Attachments are never executed, links are never followed, and remote images are never loaded.</p></div></div>
  </div>;
}

function ReportSection({id,title,count,children}:{id:string;title:string;count?:number;children:React.ReactNode}) {
  return <section id={id} className="report-section"><div className="section-heading"><h2>{title}</h2>{count !== undefined && <span>{count}</span>}</div>{children}</section>;
}
function Metric({icon,label,value}:{icon:React.ReactNode;label:string;value:string}) {return <div className="metric"><span className="metric-icon">{icon}</span><div><span>{label}</span><strong>{value}</strong></div></div>;}
function Fact({label,value,mono=false}:{label:string;value:string;mono?:boolean}) { return <div className="fact"><span>{label}</span><strong className={mono?"mono":""}>{value}</strong></div>; }
function ObservationRow({item}:{item:Observation}) { return <details className="observation" open={item.severity==="high"}>
  <summary><span className={`severity ${item.severity}`}>{item.severity}</span><span><strong>{item.title}</strong><small>{item.description}</small></span><ChevronDown/></summary>
  <div className="observation-body"><Fact label="Confidence" value={item.confidence}/><Fact label="Evidence" value={(item.evidence_reference||item.supporting_headers||[]).join(", ")||"Derived evidence"}/>
    <div><strong>Why it matters</strong><p>{item.why_it_matters||item.why_matters}</p></div><div><strong>Limitation</strong><p>{item.limitation}</p></div>
    <div><strong>Suggested action</strong><p>{item.analyst_action||item.recommended_action}</p></div></div></details>; }
function IdentityTable({parsed}:{parsed:Record<string,any>}) {
  const rows = [["From","from"],["Sender","sender"],["Reply-To","reply_to"],["Return-Path","return_path"],["To","to"],["CC","cc"]];
  return <div className="identity-table">{rows.map(([label,key]) => {const value=parsed[key]?.[0];return <div key={key}><span>{label}</span><strong>{value?.display_name||"-"}</strong><code>{value?.address||"Not present"}</code><small>{value?.domain||""}</small></div>})}
    <div><span>Message-ID</span><code>{parsed.message_id||"Not present"}</code></div></div>;
}
function AuthItem({name,value}:{name:string;value:Record<string,any>}) { const status=value.result||"none"; return <div className="auth-item"><div><span className={`status ${status}`}>{status}</span><h3>{name}</h3></div><dl><dt>Domain</dt><dd>{value.domain||"Unavailable"}</dd><dt>Evidence</dt><dd>{value.raw?"Reported in message":"Not present"}</dd></dl></div>; }
function KeyValues({title,value}:{title:string;value:Record<string,any>}) { return <details><summary>{title}</summary><div className="key-values">{Object.entries(value).map(([k,v])=><div key={k}><span>{k.replaceAll("_"," ")}</span><code>{typeof v==="object"?JSON.stringify(v):String(v ?? "Unavailable")}</code></div>)}</div></details>; }
function DataTable({rows,columns}:{rows:Array<Record<string,any>>;columns:string[]}) { return <div className="data-table"><table><thead><tr>{columns.map(x=><th key={x} scope="col">{x.replaceAll("_"," ")}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{columns.map(x=><td key={x} data-label={x.replaceAll("_"," ")}>{String(r[x]??"-")}</td>)}</tr>)}</tbody></table></div>; }
function Empty({icon,title,text}:{icon:React.ReactNode;title:string;text:string}) { return <div className="empty">{icon}<strong>{title}</strong><p>{text}</p></div>; }
function Loading() { return <div className="page"><div className="loading" role="status"><span className="spinner"/>Loading MailTrace…</div></div>; }
function PageError({message}:{message:string}) { return <div className="page"><div className="error" role="alert"><AlertTriangle/>{message}</div></div>; }
function formatBytes(bytes:number) { return bytes<1024?`${bytes} B`:bytes<1048576?`${(bytes/1024).toFixed(1)} KiB`:`${(bytes/1048576).toFixed(1)} MiB`; }

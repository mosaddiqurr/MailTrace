import { memo } from "react";
import { ArrowRight, FileCheck2, Fingerprint, Globe2, Mail, Network, Paperclip, ShieldCheck } from "lucide-react";
import { NavLink } from "react-router-dom";

function Capabilities() {
  return <section className="capabilities page" aria-labelledby="capabilities-heading">
    <div className="section-intro"><h2 id="capabilities-heading">The whole story.<br /><span>Hidden in the headers.</span></h2><p>Bring the scattered signals together in one evidence-led investigation.</p></div>
    <div className="capability-grid">
      <article className="capability capability-identity">
        <div className="identity-visual" aria-hidden="true"><div className="fingerprint-orbit"><Fingerprint size={58} strokeWidth={1} /></div><div className="auth-tokens"><span><ShieldCheck size={13} /> SPF</span><span><ShieldCheck size={13} /> DKIM</span><span><ShieldCheck size={13} /> DMARC</span></div></div>
        <div className="capability-copy"><span className="capability-icon"><Fingerprint size={18} /></span><h3>Put identity under the microscope.</h3><p>Compare sender identities, reply destinations, and reported authentication. See where the evidence aligns and where it needs a closer look.</p></div>
      </article>
      <article className="capability capability-route">
        <div className="delivery-visual" aria-hidden="true"><span><Mail size={23} /></span><i /><span><Globe2 size={23} /></span><i /><span><Network size={23} /></span></div>
        <div className="capability-copy"><span className="capability-icon"><Network size={18} /></span><h3>Retrace every recorded hop.</h3><p>Reconstruct the delivery path, inspect timestamps, and follow the message across its recorded receiving systems.</p></div>
      </article>
      <article className="capability capability-content"><Paperclip className="feature-large-icon" size={46} strokeWidth={1} /><div className="capability-copy"><h3>Inspect without interacting.</h3><p>Inventory attachments, hashes, and URLs. No executed files. No followed links. No loaded remote content.</p></div></article>
      <article className="capability capability-export"><FileCheck2 className="feature-large-icon" size={46} strokeWidth={1} /><div className="capability-copy"><h3>Evidence you can take with you.</h3><p>Export the investigation as PDF, JSON, CSV, text, HTML, or an evidence bundle. Keep the facts and their limitations together.</p></div></article>
    </div>
    <div className="methodology-callout"><div><ShieldCheck size={27} strokeWidth={1.5} /><h2>Clear findings. Honest limitations.</h2><p>Understand what the evidence tells you, and where certainty ends.</p></div><NavLink className="secondary-button" to="/methodology">Read our methodology <ArrowRight size={16} /></NavLink></div>
  </section>;
}

export default memo(Capabilities);

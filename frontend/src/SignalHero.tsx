import { memo, useEffect, useRef } from "react";
import { ArrowRight, Fingerprint } from "lucide-react";
import { NavLink } from "react-router-dom";
import { startMailSignal } from "./mailSignal";

function SignalHero() {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (canvas.current) return startMailSignal(canvas.current);
  }, []);

  return <section className="signal-hero" aria-labelledby="hero-title">
    <canvas ref={canvas} className="email-signal-canvas" aria-hidden="true" />
    <div className="hero-inner">
      <div className="hero-copy">
        <p className="hero-eyebrow"><Fingerprint size={15} /> Email forensic intelligence</p>
        <h1 id="hero-title"><span><span>Every email leaves</span></span><span><span>a trail. Follow it.</span></span></h1>
        <p className="hero-description">Look beyond the inbox. Uncover the identity, journey,<br className="desktop-break" /> and evidence behind every message.</p>
        <div className="hero-actions">
          <a className="primary hero-primary" href="#evidence">Start an investigation<span><ArrowRight size={18} /></span></a>
          <NavLink className="text-button" to="/methodology">How it works <ArrowRight size={16} /></NavLink>
        </div>
      </div>
    </div>
  </section>;
}

export default memo(SignalHero);

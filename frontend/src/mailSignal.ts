import MailSignalWorker from "./mailSignal.worker?worker";
import { createMailSignalRenderer } from "./mailSignalRenderer";

export type SignalSize = {width:number;height:number;pixelRatio:number};
export type SignalCommand = {type:"init";canvas:OffscreenCanvas} | {type:"resize";size:SignalSize} | {type:"visibility";visible:boolean};
type Renderer = {resize:(size:SignalSize)=>void;setVisible:(visible:boolean)=>void;dispose:()=>void};
type Lease = {renderer:Renderer;active:boolean};

// React StrictMode replays effects on the same canvas. A transferred canvas must reuse its worker.
const leases = new WeakMap<HTMLCanvasElement,Lease>();

function createRenderer(canvas:HTMLCanvasElement):Renderer | null {
  if(typeof Worker!=="undefined" && typeof OffscreenCanvas!=="undefined" && typeof canvas.transferControlToOffscreen==="function") {
    const worker=new MailSignalWorker();
    const send=(command:SignalCommand,transfer:Transferable[]=[])=>worker.postMessage(command,transfer);
    const surface=canvas.transferControlToOffscreen();
    send({type:"init",canvas:surface},[surface]);
    return {
      resize:size=>send({type:"resize",size}),
      setVisible:visible=>send({type:"visibility",visible}),
      dispose:()=>worker.terminate(),
    };
  }
  return createMailSignalRenderer(canvas);
}

/** Keep document/viewport observation on the page; draw the sculpture in a worker where supported. */
export function startMailSignal(canvas:HTMLCanvasElement) {
  let lease=leases.get(canvas);
  if(!lease) {
    const renderer=createRenderer(canvas);
    if(!renderer) return ()=>{};
    lease={renderer,active:true};
    leases.set(canvas,lease);
  }
  const current=lease;
  current.active=true;
  let visible=true;
  const syncVisibility=()=>current.renderer.setVisible(visible && document.visibilityState!=="hidden");
  const resize=(size?:{width:number;height:number})=>{
    const rect=size || canvas.getBoundingClientRect();
    current.renderer.resize({width:rect.width,height:rect.height,pixelRatio:window.devicePixelRatio || 1});
  };
  syncVisibility();
  resize();
  const observer=typeof ResizeObserver==="undefined" ? null : new ResizeObserver(entries=>resize(entries[0].contentRect));
  observer?.observe(canvas);
  const onResize=()=>resize();
  if(!observer) window.addEventListener("resize",onResize);
  const intersection=typeof IntersectionObserver==="undefined" ? null : new IntersectionObserver(([entry])=>{
    visible=entry.isIntersecting;
    syncVisibility();
  },{rootMargin:"-80px 0px 0px 0px"});
  intersection?.observe(canvas);
  document.addEventListener("visibilitychange",syncVisibility);
  return ()=>{
    current.active=false;
    current.renderer.setVisible(false);
    observer?.disconnect();
    intersection?.disconnect();
    window.removeEventListener("resize",onResize);
    document.removeEventListener("visibilitychange",syncVisibility);
    queueMicrotask(()=>{
      if(!current.active) {
        current.renderer.dispose();
        leases.delete(canvas);
      }
    });
  };
}

import { afterEach, describe, expect, it, vi } from "vitest";
import { startMailSignal } from "./mailSignal";

const worker=vi.hoisted(()=>({postMessage:vi.fn(),terminate:vi.fn(),created:vi.fn()}));
vi.mock("./mailSignal.worker?worker",()=>({default:class {
  constructor(){worker.created();}
  postMessage=worker.postMessage;
  terminate=worker.terminate;
}}));

afterEach(() => {vi.unstubAllGlobals();vi.restoreAllMocks();});

describe("live email sculpture", () => {
  it("transfers drawing once across a StrictMode effect replay and terminates on unmount", async()=>{
    worker.created.mockClear();worker.postMessage.mockClear();worker.terminate.mockClear();
    vi.stubGlobal("Worker",class {});
    vi.stubGlobal("OffscreenCanvas",class {});
    const canvas=document.createElement("canvas");
    const surface={} as OffscreenCanvas;
    const transfer=vi.fn(()=>surface);
    Object.defineProperty(canvas,"transferControlToOffscreen",{value:transfer});
    vi.spyOn(canvas,"getBoundingClientRect").mockReturnValue({width:1280,height:600} as DOMRect);
    const firstCleanup=startMailSignal(canvas);
    firstCleanup();
    const finalCleanup=startMailSignal(canvas);
    await Promise.resolve();
    expect(transfer).toHaveBeenCalledTimes(1);
    expect(worker.created).toHaveBeenCalledTimes(1);
    expect(worker.postMessage).toHaveBeenCalledWith({type:"init",canvas:surface},[surface]);
    expect(worker.terminate).not.toHaveBeenCalled();
    const visibility=vi.spyOn(document,"visibilityState","get").mockReturnValue("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(worker.postMessage).toHaveBeenLastCalledWith({type:"visibility",visible:false},[]);
    visibility.mockReturnValue("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(worker.postMessage).toHaveBeenLastCalledWith({type:"visibility",visible:true},[]);
    finalCleanup();
    await Promise.resolve();
    expect(worker.terminate).toHaveBeenCalledTimes(1);
  });

  it.each([[1280,600],[390,650]])("renders finite, changing geometry at %s by %s and releases its frame", (width,height) => {
    const canvas = document.createElement("canvas");
    const ctx = {
      setTransform:vi.fn(),clearRect:vi.fn(),fillRect:vi.fn(),beginPath:vi.fn(),closePath:vi.fn(),
      moveTo:vi.fn(),lineTo:vi.fn(),stroke:vi.fn(),arc:vi.fn(),rect:vi.fn(),fill:vi.fn(),
      createRadialGradient:vi.fn(()=>({addColorStop:vi.fn()})),
      createLinearGradient:vi.fn(()=>({addColorStop:vi.fn()})),
    };
    vi.spyOn(canvas,"getContext").mockReturnValue(ctx as unknown as CanvasRenderingContext2D);
    vi.spyOn(canvas,"getBoundingClientRect").mockReturnValue({width,height} as DOMRect);
    let nextFrame:FrameRequestCallback = () => {};
    let frame = 0;
    const request = vi.fn((callback:FrameRequestCallback)=>{nextFrame=callback;return ++frame;});
    const cancel = vi.fn();
    vi.stubGlobal("requestAnimationFrame",request);
    vi.stubGlobal("cancelAnimationFrame",cancel);
    const cleanup = startMailSignal(canvas);
    nextFrame(1000);
    expect(canvas.width).toBeGreaterThanOrEqual(width);
    expect(ctx.rect.mock.calls.length).toBeGreaterThan(width<621 ? 250 : 1000);
    expect(ctx.fill.mock.calls.length).toBeLessThan(200);
    for(const call of ctx.arc.mock.calls) expect(call.every(Number.isFinite)).toBe(true);
    for(const call of ctx.rect.mock.calls) expect(call.every(Number.isFinite)).toBe(true);
    const first = ctx.arc.mock.calls[0];
    ctx.arc.mockClear();
    nextFrame(2000);
    expect(ctx.arc.mock.calls[0]).not.toEqual(first);
    const paints=ctx.clearRect.mock.calls.length;
    nextFrame(2001);
    expect(ctx.clearRect.mock.calls.length).toBe(paints);
    window.dispatchEvent(new Event("resize"));
    expect(ctx.setTransform).toHaveBeenCalledTimes(1);

    const visibility=vi.spyOn(document,"visibilityState","get");
    visibility.mockReturnValue("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    nextFrame(2100);
    expect(ctx.clearRect.mock.calls.length).toBe(paints);
    visibility.mockReturnValue("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    nextFrame(2200);
    expect(ctx.clearRect.mock.calls.length).toBe(paints+1);
    cleanup();
    expect(cancel).toHaveBeenCalledWith(frame);
    const drawCount = request.mock.calls.length;
    nextFrame(3000);
    expect(request.mock.calls.length).toBe(drawCount);
  });
});

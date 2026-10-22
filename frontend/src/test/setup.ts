import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom has no canvas renderer or viewport scrolling implementation.
Object.defineProperty(HTMLCanvasElement.prototype, "getContext", { configurable: true, value: vi.fn(() => null) });
window.scrollTo = vi.fn();
Element.prototype.scrollIntoView = vi.fn();

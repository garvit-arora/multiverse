/**
 * Runs the piece: fits the 1080² stage to the window's shorter side, plays the 14-s loop on the real clock (Space or
 * R restarts it) until the first pointer move hands it to live mode, and exposes the recorder hooks: ?rec stops the
 * autoplay and live mode (the stage still fits the window), window.__render(t) shows moment t (a pure function of
 * t), window.__ready resolves when the fonts are in, window.__LOOP = 14. Reduced motion: no loop, one still moment
 * (STILL_T); live mode still works.
 */
import { createLive } from "./live";
import { createRender, type Parts } from "./render";
import { DUR } from "./timeline";
import { fontsIn } from "./fonts";

declare global {
  interface Window {
    __render?: (t: number) => void;
    __ready?: Promise<boolean>;
    __LOOP?: number;
  }
}

export type Engine = { dispose: () => void };

const SIZE = 1080;
/** The still for reduced motion: signed in, heart eyes, the antenna green, "Welcome back, Mila" */
export const STILL_T = 11.5;

export function createEngine(stage: HTMLElement, scene: HTMLElement, parts: Parts, opts: { rec: boolean; reduced: boolean; embedded?: boolean }): Engine {
  const render = createRender(parts);
  const live = createLive(parts, scene);
  window.__render = render;
  window.__LOOP = DUR;

  /* Scales the stage to the window's shorter side, in every mode (at 1080 × 1080 that is 1) */
  const fit = () => {
    const bounds = opts.embedded && stage.parentElement ? stage.parentElement.getBoundingClientRect() : null;
    const k = bounds ? Math.min(bounds.width, bounds.height) / SIZE : Math.min(innerWidth, innerHeight) / SIZE;
    // at 1 no transform at all: a scale(1) would make the stage its own layer and dither its glow differently
    stage.style.transform = k === 1 ? "" : `scale(${k})`;
  };

  let raf = 0;
  let disposed = false;
  let t0: number | null = null;
  const tick = (now: number) => {
    if (disposed) return;
    if (live.live) live.renderLive(now / 1000);
    else if (!opts.reduced) {
      if (t0 === null) t0 = now;
      render((now - t0) / 1000);
    }
    raf = requestAnimationFrame(tick);
  };
  const onKey = (e: KeyboardEvent) => {
    if (live.live || opts.reduced) return;
    if (e.code === "Space" || e.key === "r" || e.key === "R") {
      e.preventDefault();
      t0 = null;
    }
  };

  fit();
  addEventListener("resize", fit);
  const observer = opts.embedded && stage.parentElement ? new ResizeObserver(fit) : null;
  if (observer && stage.parentElement) observer.observe(stage.parentElement);
  if (!opts.rec) addEventListener("keydown", onKey);
  render(opts.reduced && !opts.rec ? STILL_T : 0);
  window.__ready = fontsIn().then(() => {
    if (disposed) return true;
    stage.dataset.ready = "";
    if (!opts.rec) {
      live.attach();
      raf = requestAnimationFrame(tick);
    }
    return true;
  });

  return {
    dispose() {
      disposed = true;
      cancelAnimationFrame(raf);
      live.detach();
      removeEventListener("resize", fit);
      observer?.disconnect();
      removeEventListener("keydown", onKey);
    },
  };
}

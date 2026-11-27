import { useEffect, type ReactNode } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ScrollSmoother } from "gsap/ScrollSmoother";

gsap.registerPlugin(ScrollTrigger, ScrollSmoother);

export function SmoothLanding({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const smoother = ScrollSmoother.create({ wrapper: "#smooth-wrapper", content: "#smooth-content", smooth: 2, effects: true, normalizeScroll: true });
    const context = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>("[data-reveal-image]").forEach((image) => gsap.fromTo(image,
        { autoAlpha: 0, scale: 1.06, filter: "blur(12px)" },
        { autoAlpha: 1, scale: 1, filter: "blur(0px)", duration: 1.15, ease: "power3.out", scrollTrigger: { trigger: image, start: "top 88%", once: true } },
      ));
    });
    return () => { context.revert(); smoother.kill(); };
  }, []);
  return <div id="smooth-wrapper"><div id="smooth-content">{children}</div></div>;
}

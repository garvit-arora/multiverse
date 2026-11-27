import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { CONTENT } from "../content";
import { drawProduct } from "../lib/product";
import { Nav } from "./Nav";
import { Ready } from "./Ready";
import styles from "./Page.module.css";

export function Page({ onGetStarted }: { onGetStarted?: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  const [product, setProduct] = useState<string>();
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let stale = false;
    Promise.all([
      drawProduct(CONTENT.art.product, "Passport"),
      ...['300 1em "Geist"', '400 1em "Geist"', '500 1em "Geist"'].map((font) => document.fonts.load(font)),
    ])
      .then(([card]) => {
        if (stale) return;
        setProduct(card as string);
        setLoaded(true);
      })
      .catch((error: unknown) => {
        console.error(error);
        if (!stale) setLoaded(true);
      });
    return () => { stale = true; };
  }, []);

  useEffect(() => {
    if (!loaded || !root.current) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const context = gsap.context(() => {
      const ready = root.current!.querySelector<HTMLElement>('[data-ready="root"]');
      const words = gsap.utils.toArray<HTMLElement>('[data-ready="root"] [data-word]');
      const text = gsap.utils.toArray<HTMLElement>('[data-ready="text"]');
      if (!ready) return;
      gsap.set(ready, { autoAlpha: 1 });

      if (reduced) {
        gsap.fromTo(
          ['[data-ready="card"]', '[data-ready="wordmark"]', ...words, ...text],
          { autoAlpha: 0 },
          { autoAlpha: 1, duration: 0.4, ease: "power1.out" },
        );
      } else {
        gsap.timeline()
          .fromTo('[data-ready="card"]', { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5, ease: "power1.out" })
          .fromTo('[data-ready="float"]',
            { rotationY: -70, rotation: 18, scale: 0.75, filter: "blur(16px) brightness(1.6)" },
            { rotationY: 0, rotation: 0, scale: 1, filter: "blur(0px) brightness(1)", duration: 1.4, ease: "power3.out", clearProps: "filter" }, 0)
          .fromTo(words,
            { autoAlpha: 0, filter: "blur(12px)", yPercent: 25 },
            { autoAlpha: 1, filter: "blur(0px)", yPercent: 0, duration: 0.7, stagger: 0.09, ease: "power2.out", clearProps: "filter,transform" }, 0.15)
          .fromTo('[data-ready="wordmark"]', { autoAlpha: 0 }, { autoAlpha: 1, duration: 1, ease: "power1.out" }, 0.4)
          .fromTo(text, { autoAlpha: 0, filter: "blur(10px)" },
            { autoAlpha: 1, filter: "blur(0px)", duration: 0.6, stagger: 0.1, ease: "power2.out", clearProps: "filter" }, 0.55);
      }

      const preventHashJump = (event: MouseEvent) => {
        if ((event.target as Element).closest?.('a[href="#"]')) event.preventDefault();
      };
      document.addEventListener("click", preventHashJump);
      return () => document.removeEventListener("click", preventHashJump);
    }, root);
    return () => context.revert();
  }, [loaded]);

  useEffect(() => () => { if (product) URL.revokeObjectURL(product); }, [product]);

  return <div ref={root} className={styles.root}><Nav theme="dark" onCta={onGetStarted}/><main><Ready product={product} onCta={onGetStarted}/></main></div>;
}

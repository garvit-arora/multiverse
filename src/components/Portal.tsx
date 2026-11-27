import { useEffect, useRef, type MutableRefObject } from "react";
import { CONTENT } from "../content";
import { IMAGE, slabCorners } from "../lib/scene";
import { lerpQuad, quadToMatrix3d, rectQuad, scaleQuad, segment, type Quad } from "../lib/quad";
import styles from "./Portal.module.css";

export type PortalState = { scale: number; face: number; flash: number; p: number };
const CARD_CORNERS = slabCorners(CONTENT.art.scene);
const inOut = (t: number) => t < .5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2;

export function Portal({ image, state }: { image?: string; state: MutableRefObject<PortalState> }) {
  const media = useRef<HTMLDivElement>(null), over = useRef<HTMLDivElement>(null), box = useRef<HTMLDivElement>(null);
  const light = useRef<HTMLDivElement>(null), plane = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let frame = 0;
    const draw = () => {
      const m = media.current, o = over.current, b = box.current, l = light.current, po = plane.current;
      if (m && o && b && l && po) {
        const s = state.current, W = m.offsetWidth, H = m.offsetHeight, bx = b.offsetLeft, by = b.offsetTop, bw = b.offsetWidth, bh = b.offsetHeight;
        m.style.transform = o.style.transform = `scale(${s.scale})`;
        const base = CARD_CORNERS.map(([x,y]) => ({ x: bx + x / IMAGE.w * bw, y: by + y / IMAGE.h * bh })) as Quad;
        const c = { x: base.reduce((a,q) => a + q.x,0)/4, y: base.reduce((a,q) => a + q.y,0)/4 };
        const d = 1 + .18 * inOut(segment(s.p,0,.7));
        b.style.transformOrigin = `${c.x-bx}px ${c.y-by}px`; b.style.transform = `scale(${d})`;
        const photo = scaleQuad(base,c,d);
        const h = ((photo[3].y-photo[0].y+photo[2].y-photo[1].y)/2)*1.06;
        const turned = lerpQuad(photo,rectQuad(c.x,c.y,h*652/1024,h),inOut(segment(s.p,0,.45)));
        const coverH = Math.max(H,W*1024/652)*1.2;
        const quad = lerpQuad(turned,rectQuad(W/2,H/2,coverH*652/1024,coverH),segment(s.p,.5,.82)**3);
        l.style.transform = po.style.transform = quadToMatrix3d(652,1024,quad);
        l.style.opacity = String(s.face*(1-segment(s.p,.15,.4)));
        po.style.setProperty("--rim",String(Math.max(s.flash,segment(s.p,.1,.4))));
        po.style.setProperty("--fill",String(segment(s.p,.35,.62)));
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw); return () => cancelAnimationFrame(frame);
  }, [state]);
  return <>
    <div ref={media} className={styles.media} data-portal="media"><div ref={box} className={styles.picture}>{image && <img src={image} alt="" />}</div></div>
    <div ref={over} className={styles.over} data-portal="over">
      <div ref={light} className={styles.light}><span className={styles.edge}/><img src="https://assets.uberdesigner.ai/portale/card-chip.svg" alt=""/><b>{CONTENT.brand}</b><strong>{CONTENT.card.name}</strong><em>{CONTENT.card.number}</em></div>
      <div ref={plane} className={styles.portal}/>
    </div>
  </>;
}

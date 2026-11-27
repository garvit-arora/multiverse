import { useEffect, useRef } from "react";
import { TEXT } from "../pipContent";
import { createEngine } from "../lib/engine";
import { SCREEN } from "../lib/led";
import s from "./PipLogin.module.css";

const REC = new URLSearchParams(location.search).has("rec") || location.hash == "#rec";
/** The arrow cursor (drawn in a 30 px box from a 256 viewBox), black with a white rim */
const ARROW =
  "M220.49,207.8,207.8,220.49a12,12,0,0,1-17,0l-56.57-56.57L115,214.08l-.13.33A15.84,15.84,0,0,1,100.26,224l-.78,0a15.82,15.82,0,0,1-14.41-11L32.8,52.92A15.95,15.95,0,0,1,52.92,32.8L213,85.07a16,16,0,0,1,1.41,29.8l-.33.13-50.16,19.27,56.57,56.56A12,12,0,0,1,220.49,207.8Z";

/** Pip login: a sign-in card with a little robot peeking over it, on a 1080² stage */
export function PipLogin({ onSuccess, embedded = false }: { onSuccess?: () => void; embedded?: boolean }) {
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = stage.current;
    if (!root) return;
    /** The layer marked data-part={name} */
    const part = <T extends Element = HTMLElement>(name: string) => root.querySelector<T>(`[data-part="${name}"]`)!;
    const parts = (name: string) => [...root.querySelectorAll<HTMLElement>(`[data-part="${name}"]`)];
    const led = part<HTMLCanvasElement>("led").getContext("2d"),
      ledGlow = part<HTMLCanvasElement>("ledGlow").getContext("2d");
    if (!led || !ledGlow) return;
    const [handL, handR] = parts("hand");
    const [b1, b2, b3] = parts("label");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const e = createEngine(
      root,
      part("scene"),
      {
        cursor: part("cursor"),
        cursorArrow: part<SVGSVGElement>("arrow"),
        pip: part("pip"),
        antenna: part("antenna"),
        glow: part("glow"),
        halo: part("halo"),
        earLights: parts("earLight"),
        led,
        ledGlow,
        hands: [handL, handR],
        emailField: part("emailField"),
        passwordField: part("passwordField"),
        emailValue: part("emailValue"),
        passwordValue: part("passwordValue"),
        emailCaret: part("emailCaret"),
        passwordCaret: part("passwordCaret"),
        error: part("error"),
        button: part("button"),
        labels: [b1, b2, b3],
        spinner: part("spinner"),
        focused: s.focused,
      },
      { rec: REC, reduced, embedded },
    );
    const button = part("button");
    let completionTimer = 0;
    const complete = () => { completionTimer = window.setTimeout(() => onSuccess?.(), 1050); };
    button.addEventListener("click", complete);
    return () => {
      button.removeEventListener("click", complete);
      window.clearTimeout(completionTimer);
      e.dispose();
    };
  }, [onSuccess, embedded]);

  const hand = (
    <div className={s.hand} data-part="hand">
      <div className={s.palm} />
      <div className={s.finger} style={{ left: 16 }} />
      <div className={s.finger} style={{ left: 24 }} />
      <div className={s.finger} style={{ left: 32 }} />
    </div>
  );

  return (
    <div className={s.stage} ref={stage} role="img" aria-label={TEXT.scene}>
      <div className={s.scene} data-part="scene">
        <div className={s.pip} data-part="pip">
          <div className={`${s.ear} ${s.earLeft}`}>
            <i className={s.earSlot} />
            <b className={s.earLight} data-part="earLight" />
          </div>
          <div className={`${s.ear} ${s.earRight}`}>
            <i className={s.earSlot} />
            <b className={s.earLight} data-part="earLight" />
          </div>
          <div className={s.antenna} data-part="antenna">
            <div className={s.stem} />
            <div className={s.halo} data-part="halo" />
            <div className={s.ball} />
            <div className={s.glow} data-part="glow" />
          </div>
          <div className={s.head}>
            <div className={s.spec} />
            <div className={s.bezel} />
            <div className={s.screen}>
              <canvas className={s.ledGlow} data-part="ledGlow" width={SCREEN.w * SCREEN.dpr} height={SCREEN.h * SCREEN.dpr} />
              <canvas className={s.led} data-part="led" width={SCREEN.w * SCREEN.dpr} height={SCREEN.h * SCREEN.dpr} />
              <div className={s.glass} />
              <div className={s.arc} />
            </div>
          </div>
        </div>

        <div className={s.card}>
          <div className={s.cap}>{TEXT.cap}</div>
          <h1 className={s.title}>{TEXT.title}</h1>
          <div className={`${s.field} ${s.fieldEmail}`} data-part="emailField">
            <span className={s.label}>{TEXT.email}</span>
            <span className={s.value} data-part="emailValue" />
            <span className={s.caret} data-part="emailCaret" />
            <span className={s.error} data-part="error">
              {TEXT.error}
            </span>
          </div>
          <div className={`${s.field} ${s.fieldPassword}`} data-part="passwordField">
            <span className={s.label}>{TEXT.password}</span>
            <span className={s.dots} data-part="passwordValue" />
            <span className={s.caret} data-part="passwordCaret" />
          </div>
          <div className={s.button} data-part="button">
            <span className={s.buttonLabel} data-part="label">
              {TEXT.signIn}
            </span>
            <span className={s.buttonLabel} data-part="label">
              <i className={s.spinner} data-part="spinner" />
              {TEXT.checking}
            </span>
            <span className={s.buttonLabel} data-part="label">
              {TEXT.welcome}
            </span>
          </div>
        </div>

        {hand}
        {hand}

        <div className={s.cursor} data-part="cursor">
          <svg data-part="arrow" width="30" height="30" viewBox="0 0 256 256" fill="currentColor">
            <path fill="#151515" stroke="#fff" strokeWidth="14" paintOrder="stroke" d={ARROW} />
          </svg>
        </div>
      </div>
    </div>
  );
}

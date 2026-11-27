/**
 * render(t): writes moment t (seconds, any value; wrapped to the 14-s loop) onto the layers. A pure function of t:
 * every style it ever sets it sets on every call, so any frame can be drawn on its own, in any order.
 */
import { GAZE_CHARS, TEXT } from "../pipContent";
import { bitmap, drawLED, free, type Expr } from "./led";
import { L, TAU, cl, sm } from "./math";
import { DUR, ERR, EX, EYE_AT, cursorAt, handPose, headMotion, nEmail, nPassword, pressedAt } from "./timeline";

export type Parts = {
  cursor: HTMLElement;
  cursorArrow: SVGSVGElement;
  pip: HTMLElement;
  antenna: HTMLElement;
  glow: HTMLElement;
  halo: HTMLElement;
  earLights: HTMLElement[];
  led: CanvasRenderingContext2D;
  ledGlow: CanvasRenderingContext2D;
  hands: [HTMLElement, HTMLElement];
  emailField: HTMLElement;
  passwordField: HTMLElement;
  emailValue: HTMLElement;
  passwordValue: HTMLElement;
  emailCaret: HTMLElement;
  passwordCaret: HTMLElement;
  error: HTMLElement;
  button: HTMLElement;
  labels: [HTMLElement, HTMLElement, HTMLElement];
  spinner: HTMLElement;
  /** The CSS Module class of a focused field */
  focused: string;
};

/** The red state of the antenna ball, its halo and the ear lights (the green ones are in the stylesheet) */
export const RED = {
  glow: "radial-gradient(circle at 36% 32%,#fff1ef 0 16%,#ff7a6e 52%,#e5484d 100%)",
  halo: "radial-gradient(circle,rgba(255,110,100,.55),rgba(255,110,100,0) 70%)",
  ear: "#ff6b61",
  earGreen: "#8ff0c2",
};
const ERR_BORDER = (er: number) => `rgba(229,72,77,${0.35 + 0.65 * er})`;
const ERR_FILL = (er: number) => `rgba(255,240,239,${er})`;
const BTN = { rest: "#151515", hover: "#2b2b2b" };

export function createRender(p: Parts) {
  const E1 = TEXT.e1,
    E2 = TEXT.e2,
    EMAIL = E1 + E2;
  return function render(t: number) {
    t = ((t % DUR) + DUR) % DUR;
    const [mx, my] = cursorAt(t);
    p.cursor.style.transform = `translate(${mx}px,${my}px)`;
    p.cursorArrow.style.transform = `scale(${pressedAt(t) ? 0.86 : 1})`;
    const M = headMotion(t);

    // the gaze, in dots: reading along the email, down-left while crossed, else toward the cursor, else wandering
    let gx: number, gy: number;
    const on = mx < 1080 && my < 1100,
      nE = nEmail(t, E1.length, E2.length);
    if ((t > 2.45 && t < 3.9) || (t > 5.75 && t < 6.2)) {
      gx = -2 + (nE / GAZE_CHARS) * 3.4;
      gy = 2;
    } else if (t > 4.3 && t < 5.6) {
      gx = -1.5;
      gy = 2;
    } else if (on) {
      const dx = mx - EYE_AT.x,
        dy = my - EYE_AT.y,
        d = Math.hypot(dx, dy);
      gx = (dx / Math.max(d, 1)) * Math.min(1, d / 200) * 2.4;
      gy = (dy / Math.max(d, 1)) * Math.min(1, d / 200) * 2.4;
    } else {
      gx = 1.6 * Math.sin(((t * TAU) / 7) * 2);
      gy = 0.5 * Math.sin((t * TAU) / 7);
    }

    // the face: cross-fade from the previous expression to the current one
    let ia = 0;
    for (let i = 0; i < EX.length; i++) if (t >= EX[i][0]) ia = i;
    const pv = EX[(ia + EX.length - 1) % EX.length][1],
      cu = EX[ia][1],
      since = t - EX[ia][0];
    const R = (n: Expr): [number, number] => (free(n) ? [Math.round(gx), Math.round(gy)] : [0, 0]);
    const A = bitmap(pv, ...R(pv), t);
    let B = bitmap(cu, ...R(cu), t);
    // the peek: the left eye looks out (idle, shifted down-left) while the right stays shy
    const pk = sm(cl((t - 7.8) / 0.14)) * (1 - sm(cl((t - 8.12) / 0.14)));
    if (pk > 0) {
      const P = bitmap("idle", -1, 2, t, [1, 0]),
        S = bitmap("shy", 0, 0, t, [0, 1]);
      const M2 = P.map((v, i) => Math.max(v, S[i]));
      B = B.map((v, i) => L(v, M2[i], pk));
    }
    drawLED(p.led, p.ledGlow, A, B, cu == "blink" || pv == "blink" ? cl(since / 0.08) * 1.5 : cl(since / 0.34));

    // the body, and the antenna lagging behind it (from the motion 0.07 s ago)
    p.pip.style.transform = `translateY(${M.ty}px) rotate(${M.rot}deg) scale(${M.sx},${M.sy})`;
    const Mp = headMotion((((t - 0.07) % DUR) + DUR) % DUR),
      vel = M.ty - Mp.ty,
      rv = M.rot - Mp.rot;
    p.antenna.style.transform = `rotate(${-rv * 6 - vel * 0.9 + 2.5 * Math.sin((t * TAU) / 2 + 1)}deg)`;

    // antenna ball, halo and ear lights: green from the hover to the welcome (pulsing while checking), red on error
    const er = ERR(t);
    const glow = t > 9.55 && t < 12.2 ? sm(cl((t - 9.55) / 0.25)) * (1 - sm(cl((t - 11.8) / 0.4))) : 0;
    const pulse = t > 10.25 && t < 11.1 ? 0.6 + 0.4 * Math.sin((t - 10.25) * TAU * 2.4) : 1;
    p.glow.style.opacity = String(Math.max(glow * pulse, er));
    p.halo.style.opacity = String(Math.max(glow * pulse, er) * 0.9);
    const red = er > 0.01;
    p.glow.style.background = red ? RED.glow : "";
    p.halo.style.background = red ? RED.halo : "";
    p.earLights.forEach((b) => {
      b.style.opacity = String(Math.max(glow * pulse, er));
      b.style.background = red ? RED.ear : RED.earGreen;
    });

    // the hands ride on the card edge (lifting with Pip), or cover the screen and move with him
    handPose(t).forEach(([x, y, k], i) => {
      const h = p.hands[i];
      const lift = Math.min(0, M.ty * 0.1) * (1 - k);
      h.style.transform = `translate(${x + M.rot * 0.6 * (1 - k)}px,${y + lift + M.ty * k}px) rotate(${(i ? -1 : 1) * -14 * k}deg) scale(${1 + 0.35 * k})`;
    });

    // fields: focus, the error's red and shake, the hint
    const fe = (t > 2.3 && t < 4.25) || (t > 5.6 && t < 6.9),
      fp = (t > 4.25 && t < 5.6) || (t > 6.9 && t < 10.2);
    p.emailField.classList.toggle(p.focused, fe && er < 0.5);
    p.passwordField.classList.toggle(p.focused, fp);
    const fEl = p.emailField;
    fEl.style.borderColor = er > 0.01 ? ERR_BORDER(er) : "";
    fEl.style.background = er > 0.01 ? ERR_FILL(er) : "";
    const sh = t > 4.3 && t < 4.9 ? 7 * Math.sin((t - 4.3) * TAU * 6) * Math.exp(-5 * (t - 4.3)) : 0;
    fEl.style.transform = `translateX(${sh}px)`;
    p.error.style.opacity = String(er);
    p.error.style.transform = `translateY(${(1 - er) * 6}px)`;
    p.error.style.filter = er < 0.99 ? `blur(${(1 - er) * 4}px)` : "none";

    // the typed values fade out at 13.2 – 13.6 and clear
    const fade = t > 13.2 ? 1 - sm(cl((t - 13.2) / 0.4)) : 1,
      clear = t > 13.6;
    p.emailValue.textContent = clear ? "" : EMAIL.slice(0, nE);
    p.emailValue.style.opacity = String(fade);
    p.passwordValue.textContent = clear ? "" : "•".repeat(nPassword(t));
    p.passwordValue.style.opacity = String(fade);
    const blinkC = Math.floor(t * 2.5) % 2 == 0;
    p.emailCaret.style.opacity = fe && blinkC ? "1" : "0";
    p.passwordCaret.style.opacity = fp && blinkC ? "1" : "0";

    // the button: Sign in → Checking (10.25 – 11.05) → Welcome back, Mila (11.1 – 13.5)
    const k1 = sm(cl((t - 10.25) / 0.25)) * (1 - sm(cl((t - 11.05) / 0.2)));
    const k2 = t > 11 && t < 13.6 ? sm(cl((t - 11.1) / 0.3)) * (1 - sm(cl((t - 13.15) / 0.35))) : 0;
    const hov = t > 9.55 && t < 10.3;
    p.button.style.background = hov ? BTN.hover : BTN.rest;
    p.button.style.transform = `scale(${pressedAt(t) && t > 10 ? 0.97 : 1})`;
    const st = (el: HTMLElement, v: number, dir: number) => {
      el.style.opacity = String(v);
      el.style.transform = `translateY(${(1 - v) * 22 * dir}px)`;
      el.style.filter = v < 0.99 ? `blur(${(1 - v) * 6}px)` : "none";
    };
    st(p.labels[0], 1 - Math.max(k1, k2), -1);
    st(p.labels[1], k1, 1);
    st(p.labels[2], k2, 1);
    p.spinner.style.transform = `rotate(${t * 720}deg)`;
  };
}

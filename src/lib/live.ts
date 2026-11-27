/**
 * Live mode: the first pointer move over the page ends the autoplay and hands Pip to the visitor. Click the email or
 * password field and type (Tab switches, Backspace deletes); Pip reads along, objects to an email with no domain
 * when you leave its field, hides behind his hands while the password field has focus, gets star eyes over Sign in,
 * spins and then shows hearts when you click it, and dozes off after 5 s without input.
 */
import { bitmap, drawLED, free, type Expr } from "./led";
import { L, TAU, cl, sm } from "./math";
import { RED, type Parts } from "./render";
import { COVER, EYE_AT, REST } from "./timeline";

type FieldId = "fe" | "fp" | null;
/** A complete-looking email: something, @, something, a dot, something */
const EMAIL_OK = /@.+\..+/;
const HAND_SPRING = "transform .35s cubic-bezier(.3,1.2,.4,1)";

export function createLive(p: Parts, scene: HTMLElement) {
  const LV = { err: -9, x: 0, y: 0, last: 0, tap: -9, expr: "idle" as Expr, prev: "idle" as Expr, at: 0, typing: -9 };
  let live = false;
  let focusF: FieldId = null;

  /** Pointer position in scene px */
  const toScene = (e: PointerEvent): [number, number] => {
    const r = scene.getBoundingClientRect(),
      k = r.width / 1080;
    return [(e.clientX - r.left) / k, (e.clientY - r.top) / k];
  };
  const inside = (el: HTMLElement, x: number, y: number) => {
    const r = el.getBoundingClientRect(),
      s = scene.getBoundingClientRect(),
      k = s.width / 1080;
    return x > (r.left - s.left) / k && x < (r.right - s.left) / k && y > (r.top - s.top) / k && y < (r.bottom - s.top) / k;
  };
  const now = () => performance.now() / 1000;
  const checkEmail = () => {
    const v = p.emailValue.textContent ?? "";
    if (v && !EMAIL_OK.test(v)) LV.err = now();
  };

  const onMove = (e: PointerEvent) => {
    if (!live) {
      live = true;
      p.emailValue.textContent = "";
      p.passwordValue.textContent = "";
      // the loop may have been fading them out
      p.emailValue.style.opacity = "1";
      p.passwordValue.style.opacity = "1";
    }
    [LV.x, LV.y] = toScene(e);
    LV.last = now();
  };
  const onDown = (e: PointerEvent) => {
    if (!live) return;
    const [x, y] = toScene(e);
    const n = now();
    LV.last = n;
    const was = focusF;
    if (inside(p.emailField, x, y)) focusF = "fe";
    else if (inside(p.passwordField, x, y)) focusF = "fp";
    else if (inside(p.button, x, y)) {
      LV.tap = n;
      focusF = null;
    } else focusF = null;
    if (was == "fe" && focusF != "fe") checkEmail();
  };
  const onKey = (e: KeyboardEvent) => {
    if (!live || !focusF) return;
    const n = now();
    LV.typing = n;
    LV.last = n;
    const el = focusF == "fe" ? p.emailValue : p.passwordValue;
    const v = el.textContent ?? "";
    if (e.key == "Backspace") el.textContent = v.slice(0, -1);
    else if (e.key == "Tab") {
      e.preventDefault();
      if (focusF == "fe") checkEmail();
      focusF = focusF == "fe" ? "fp" : "fe";
    } else if (e.key.length == 1) el.textContent = v + (focusF == "fe" ? e.key : "•");
  };

  /** Draws the live state at n (seconds, the real clock) */
  function renderLive(n: number) {
    p.cursor.style.display = "none";
    p.emailField.classList.toggle(p.focused, focusF == "fe");
    p.passwordField.classList.toggle(p.focused, focusF == "fp");
    const bl = Math.floor(n * 2.5) % 2 == 0;
    p.emailCaret.style.opacity = focusF == "fe" && bl ? "1" : "0";
    p.passwordCaret.style.opacity = focusF == "fp" && bl ? "1" : "0";
    const dx = LV.x - EYE_AT.x,
      dy = LV.y - EYE_AT.y,
      d = Math.hypot(dx, dy);
    let gx = (dx / Math.max(d, 1)) * Math.min(1, d / 200) * 2.4,
      gy = (dy / Math.max(d, 1)) * Math.min(1, d / 200) * 2.4;
    const over = inside(p.button, LV.x, LV.y),
      tu = n - LV.tap,
      cover = focusF == "fp";
    const typed = (p.emailValue.textContent ?? "").length;
    if (focusF == "fe" && n - LV.typing < 1.2) {
      gx = -2 + Math.min(1, typed / 16) * 3.2;
      gy = 2;
    }
    const eu = n - LV.err;
    const want: Expr =
      eu < 1.8
        ? "cross"
        : tu < 0.6
          ? "load"
          : tu < 2
            ? "heart"
            : cover
              ? "shy"
              : focusF == "fe" && n - LV.typing < 1.2
                ? "read"
                : over
                  ? "star"
                  : n - LV.last > 5
                    ? "sleepy"
                    : Math.floor(n * 10) % 41 == 0
                      ? "blink"
                      : "idle";
    if (want != LV.expr) {
      LV.prev = LV.expr;
      LV.expr = want;
      LV.at = n;
    }
    const since = n - LV.at,
      R = (x: Expr): [number, number] => (free(x) ? [Math.round(gx), Math.round(gy)] : [0, 0]);
    drawLED(p.led, p.ledGlow, bitmap(LV.prev, ...R(LV.prev), n), bitmap(LV.expr, ...R(LV.expr), n), want == "blink" ? 1 : cl(since / 0.34));

    let ty = 2 * Math.sin((n * TAU) / 2),
      rot = Math.max(-1, Math.min(1, dx / 400)) * 5;
    if (over) ty -= 12;
    if (tu > 0.6 && tu < 1.2) ty -= 36 * Math.sin((Math.PI * (tu - 0.6)) / 0.6);
    if (LV.expr == "sleepy") ty += 24 * sm(cl(since / 0.6));
    if (cover) ty += 8;
    if (n - LV.typing < 0.15) ty -= 3;
    if (eu < 1.2) rot += 9 * Math.sin(eu * TAU * 2.2) * Math.exp(-2.2 * eu);

    const ee = eu < 1.8;
    p.emailField.style.borderColor = ee ? "#e5484d" : "";
    p.emailField.style.background = ee ? "#fff0ef" : "";
    p.emailField.style.transform = "translateX(0px)";
    p.error.style.opacity = ee ? "1" : "0";
    p.error.style.transform = "none";
    p.error.style.filter = "none";
    p.pip.style.transform = `translateY(${ty}px) rotate(${rot}deg)`;
    p.antenna.style.transform = `rotate(${-rot * 1.4}deg)`;

    const g = over || tu < 2 || ee ? 1 : 0;
    p.glow.style.opacity = String(g);
    p.halo.style.opacity = String(g * 0.9);
    p.glow.style.background = ee ? RED.glow : "";
    p.halo.style.background = ee ? RED.halo : "";
    p.earLights.forEach((b) => {
      b.style.opacity = String(g);
      b.style.background = ee ? RED.ear : RED.earGreen;
    });
    p.hands.forEach((h, i) => {
      const k = cover ? 1 : 0;
      h.style.transition = HAND_SPRING;
      h.style.transform = `translate(${L(REST[i][0], COVER[i][0], k)}px,${L(REST[i][1], COVER[i][1], k) + ty * k}px) rotate(${(i ? -1 : 1) * -14 * k}deg) scale(${1 + 0.35 * k})`;
    });

    const [b1, b2, b3] = p.labels;
    b1.style.opacity = tu < 0.6 || tu < 2 ? "0" : "1";
    b2.style.opacity = tu < 0.6 ? "1" : "0";
    b2.style.transform = "none";
    b3.style.opacity = tu > 0.6 && tu < 2.2 ? "1" : "0";
    b3.style.transform = "none";
    b1.style.transform = "none";
    b1.style.filter = b2.style.filter = b3.style.filter = "none";
    p.spinner.style.transform = `rotate(${n * 720}deg)`;
    p.button.style.background = over ? "#2b2b2b" : "#151515";
    p.button.style.transform = "scale(1)";
  }

  return {
    get live() {
      return live;
    },
    renderLive,
    attach() {
      addEventListener("pointermove", onMove);
      addEventListener("pointerdown", onDown);
      addEventListener("keydown", onKey);
    },
    detach() {
      removeEventListener("pointermove", onMove);
      removeEventListener("pointerdown", onDown);
      removeEventListener("keydown", onKey);
    },
  };
}

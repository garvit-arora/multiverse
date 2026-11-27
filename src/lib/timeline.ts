/**
 * The 14-second script, in scene coordinates (the 1080² scene before its 1.18 zoom). Every beat is a number here:
 * 0     cursor waits off-stage bottom right; Pip idles, blinks at 0.8
 * 1.4   cursor sweeps in (bowed path) to the email field, click 2.3; Pip reads from 2.45 while "mila@quelm" types
 * 4.25  click on the password field without a domain: Pip's eyes cross, he shakes "no", the field turns red and
 *       shakes, "Add the domain" fades in, the antenna and ears glow red
 * 5.6   back to the email field: ".so" is typed, Pip reads again, then a happy nod at 6.2
 * 6.9   password field: Pip covers his screen with both hands (shy), the right hand lifts 7.75 – 8.35 and one eye
 *       peeks out 7.8 – 8.12; 8 dots typed
 * 9.5   cursor hovers Sign in: star eyes, Pip rises, antenna glows green; click 10.2 → "Checking" with a loading ring
 * 11.1  "Welcome back, Mila": heart eyes, Pip jumps and squashes; 12.2 happy, 12.9 sleepy (he sinks), cursor leaves,
 *       fields fade at 13.2 and clear at 13.6, blink 13.65, idle by 14 = 0
 */
import { type Expr } from "./led";
import { L, TAU, cl, eio, sm } from "./math";

export const DUR = 14;

/** Cursor keys: [time, x, y]; eased in-out between keys; the moves from key 1 and from key 9 bow upward 70 and 24 px */
const CP: [number, number, number][] = [
  [0, 1180, 1000],
  [1.4, 1180, 1000],
  [2.3, 330, 602],
  [3.95, 330, 602],
  [4.25, 330, 670],
  [5.25, 330, 670],
  [5.6, 520, 602],
  [6.5, 520, 602],
  [6.9, 330, 670],
  [8.7, 330, 670],
  [9.5, 600, 744],
  [10.2, 600, 744],
  [11.6, 1010, 980],
  [12.3, 1180, 1120],
  [14, 1180, 1120],
];
export function cursorAt(t: number): [number, number] {
  for (let i = 0; i < CP.length - 1; i++) {
    const [a, x0, y0] = CP[i],
      [b, x1, y1] = CP[i + 1];
    if (t >= a && t <= b) {
      const k = eio((t - a) / (b - a));
      const bow = Math.sin(Math.PI * k) * (i == 1 ? -70 : i == 9 ? -24 : 0);
      return [L(x0, x1, k), L(y0, y1, k) + bow];
    }
  }
  return [1180, 1120];
}

/** Pip's expressions: [from time, expression]; each cross-fades in over 0.34 s (a blink over 0.08 s) */
export const EX: [number, Expr][] = [
  [0, "idle"],
  [0.8, "blink"],
  [0.92, "idle"],
  [2.45, "read"],
  [4.0, "idle"],
  [4.3, "cross"],
  [5.6, "idle"],
  [5.75, "read"],
  [6.2, "happy"],
  [6.95, "shy"],
  [8.85, "idle"],
  [9.55, "star"],
  [10.25, "load"],
  [11.1, "heart"],
  [12.2, "happy"],
  [12.9, "sleepy"],
  [13.65, "blink"],
  [13.78, "idle"],
];

/** The typed email comes in two parts: E1 before the error, E2 (the domain's ending) after it */
export const PWN = 8; // password dots
const CLICKS = [2.3, 4.25, 5.6, 6.9, 10.2];
/** The cursor shrinks to 0.86 for 0.14 s after each click */
export const pressedAt = (t: number) => CLICKS.some((c) => t > c && t < c + 0.14);
/** The error's level, 0 … 1: in 4.3 – 4.5, out 5.95 – 6.15 */
export const ERR = (t: number) => (t > 4.3 && t < 6.15 ? sm(cl((t - 4.3) / 0.2)) * (1 - sm(cl((t - 5.95) / 0.2))) : 0);
/** How many characters of the email show: E1 at 0.12 s a key from 2.5, E2 at 0.13 s a key from 5.75 */
export function nEmail(t: number, e1: number, e2: number) {
  if (t < 2.5) return 0;
  if (t < 5.75) return Math.min(e1, Math.floor((t - 2.5) / 0.12) + 1);
  return e1 + Math.min(e2, Math.floor((t - 5.75) / 0.13) + 1);
}
/** How many password dots show: one each 0.15 s from 7.25 */
export const nPassword = (t: number) => (t < 7.25 ? 0 : Math.min(PWN, Math.floor((t - 7.25) / 0.15) + 1));

/** Pip's body: a 2-s bob, leaning toward the cursor, and every beat's hop, shake, nod, rise, jump and sink */
export function headMotion(t: number) {
  let ty = 2 * Math.sin((t * TAU) / 2),
    rot = 0,
    sx = 1,
    sy = 1;
  const [mx, my] = cursorAt(t),
    on = mx < 1080 && my < 1100;
  rot = (on ? Math.max(-1, Math.min(1, (mx - 740) / 400)) : Math.sin((t * TAU) / 7) * 0.6) * 5;
  // a little hop on each typed key
  if ((t > 2.5 && t < 3.75) || (t > 5.75 && t < 6.15)) {
    const kk = (t - (t < 5 ? 2.5 : 5.75)) / 0.12;
    ty += -3 * Math.max(0, Math.sin(kk * Math.PI));
  }
  // shakes "no"
  if (t > 4.3 && t < 5.4) {
    const u = t - 4.3;
    rot += 9 * Math.sin(u * TAU * 2.2) * Math.exp(-2.2 * u);
    ty += 6 * sm(cl(u / 0.2)) * (1 - sm(cl((u - 0.8) / 0.3)));
  }
  // relieved nod
  if (t > 6.2 && t < 6.9) {
    const u = t - 6.2;
    ty -= 8 * Math.sin(Math.PI * cl(u / 0.35));
  }
  // ducks behind his hands
  if (t > 6.95 && t < 8.85) ty += 8 * sm(cl((t - 6.95) / 0.3)) * (1 - sm(cl((t - 8.6) / 0.25)));
  // rises to the button
  if (t > 9.55 && t < 10.25) ty -= 14 * sm(cl((t - 9.55) / 0.3));
  // sways while checking
  if (t >= 10.25 && t < 11.1) {
    ty -= 14;
    rot += 3 * Math.sin((t - 10.25) * TAU * 1.4);
  }
  // jumps for joy, squashes on take-off and landing
  if (t >= 11.1 && t < 12.2) {
    const u = t - 11.1;
    let h = -14 - 38 * Math.sin(Math.PI * cl(u / 0.46));
    if (u > 0.46) h = -14 + 12 * Math.exp(-5 * (u - 0.46)) * Math.sin((u - 0.46) * 14);
    ty += L(h, 0, sm(cl((u - 0.65) / 0.45)));
    const sq = u < 0.08 ? u / 0.08 : u > 0.44 && u < 0.56 ? 1 - (u - 0.44) / 0.12 : 0;
    sx = 1 + 0.05 * sq;
    sy = 1 - 0.05 * sq;
  }
  // sinks, sleepy, and comes back up
  const sink = t > 12.9 ? sm(cl((t - 12.9) / 0.6)) * (1 - sm(cl((t - 13.5) / 0.45))) : 0;
  ty += 24 * sink;
  rot *= 1 - sink;
  return { ty, rot, sx, sy };
}

/** The hands: resting on the card's top edge, or covering the screen (scene px, top-left of a 48 × 32 hand) */
export const REST: [number, number][] = [
  [648, 420],
  [792, 420],
];
export const COVER: [number, number][] = [
  [684, 352],
  [748, 352],
];
/** [x, y, cover 0 … 1] per hand; the right hand lifts a little (55 %) for the peek at 7.75 – 8.35 */
export function handPose(t: number): [number, number, number][] {
  const c = sm(cl((t - 6.95) / 0.35)) * (1 - sm(cl((t - 8.5) / 0.35)));
  const peek = sm(cl((t - 7.75) / 0.2)) * (1 - sm(cl((t - 8.15) / 0.2)));
  return [0, 1].map((i) => {
    const k = i == 1 ? c * (1 - peek * 0.55) : c;
    return [L(REST[i][0], COVER[i][0], k), L(REST[i][1], COVER[i][1], k), k];
  });
}

/** Where Pip's eyes look from (scene px): the cursor's direction from here sets the gaze */
export const EYE_AT = { x: 740, y: 380 };

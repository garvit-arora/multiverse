/** The faces the piece uses: Geist 400 and 500, Geist Mono 500 (the caption) */
const FACES = ['400 20px "Geist"', '500 20px "Geist"', '500 16px "Geist Mono"'];
const WAIT_AT_MOST = 1500; // ms: a slow or blocked font doesn't hold the piece back for longer

/** Resolves once the faces are in, or after 1.5 s, or at once if they fail to load */
export function fontsIn(): Promise<void> {
  return Promise.race([
    Promise.all(FACES.map((face) => document.fonts.load(face))),
    new Promise((done) => setTimeout(done, WAIT_AT_MOST)),
  ]).then(
    () => undefined,
    () => undefined,
  );
}

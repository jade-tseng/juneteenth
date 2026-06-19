# UI.md — Design Specification

**Product:** Voice-to-ASL Signing Avatar (POC)
**For:** `renderer-agent` (3D stage) + `demo-agent` (glass UI, states, caption)
**Direction:** Apple-clean, minimal, glass. The 3D avatar is the hero. Everything fluid and continuous.

---

## 1. Design thesis
The signing avatar stands on a softly-lit stage and *is* the interface. UI is quiet translucent glass that floats at the edges and recedes. The live caption — the words being signed — is the single editorial moment, set large and light like refined film subtitles. Nothing competes with the figure. The 3D canvas and the CSS surfaces share one palette so the whole screen reads as a single lit space, not "a 3D view with UI on top."

**Signature element:** the caption that breathes — words crossfade in word-by-word, in sync with the signing motion, in a large light display weight. That is the one thing this app is remembered by.

**Where the boldness is spent:** the caption typography + the luminous stage. Everything else stays disciplined and near-invisible.

---

## 2. Principles
- **Restraint over decoration.** If an element doesn't help the person speak, watch, or replay — cut it.
- **One accent, used rarely.** Interest comes from light, translucency, and space, not color.
- **Continuity.** The 3D environment and the CSS environment use the same colors and the same easing. The blur behind glass is the real stage.
- **Fluid, calm motion.** Slow, eased, continuous. Never bouncy, never frantic, never "fun-app."
- **Match the build's continuity.** The avatar's motion is slerp-blended and seamless (per the build spec); the UI motion should feel like the same physics.

---

## 3. Color tokens
Dark, cool, atmospheric — not flat black, not neon-accented.

```css
:root {
  /* Environment */
  --bg-void:        #0A0C10;   /* deepest base */
  --bg-stage-top:   #171B22;   /* top of stage gradient */
  --bg-stage-glow:  #242C3A;   /* soft radial light behind the avatar */

  /* Glass material */
  --glass-fill:        rgba(255,255,255,0.055);
  --glass-fill-hover:  rgba(255,255,255,0.090);
  --glass-stroke:      rgba(255,255,255,0.12);
  --glass-highlight:   rgba(255,255,255,0.18);  /* top-edge light catch */

  /* Text */
  --text-primary:   #EEF1F6;   /* soft white, never pure #fff */
  --text-secondary: rgba(238,241,246,0.55);
  --text-tertiary:  rgba(238,241,246,0.32);

  /* Accent — active/focus ONLY, used sparingly */
  --accent:         #93A7FF;   /* desaturated periwinkle */
  --accent-glow:    rgba(147,167,255,0.30);

  /* Feedback */
  --danger:         #FF9A9A;   /* soft, for errors */
}
```

Stage background:
```css
background:
  radial-gradient(120% 80% at 50% 38%, var(--bg-stage-glow) 0%, transparent 60%),
  linear-gradient(180deg, var(--bg-stage-top) 0%, var(--bg-void) 100%);
```

> A documented light variant is possible (swap fills/text), but **dark is the spec** — the avatar reads best against it and the glass looks most premium.

---

## 4. Typography
**One family, hierarchy through weight / size / tracking.** This is deliberate (Apple uses essentially one system family across the OS) — not a default shortcut. No webfont needed; the platform face is the authentic choice here.

```css
--font-ui:      -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", system-ui, sans-serif;
--font-display: -apple-system, "SF Pro Display", "Inter", system-ui, sans-serif;
```

| Role | Size | Weight | Tracking | Notes |
|------|------|--------|----------|-------|
| Caption (hero) | clamp(1.75rem, 4.2vw, 3rem) | 300 | -0.01em | line-height 1.15; the signature |
| Wordmark | 0.95rem | 500 | 0.02em | lowercase |
| Control label | 0.8125rem | 500 | 0.01em | sentence case |
| Secondary / status | 0.8125rem | 400 | 0 | --text-secondary |
| Data (speed) | 0.75rem | 500 | 0.02em | tabular-nums |

Body/UI uses sentence case throughout. No all-caps except none — keep it quiet.

---

## 5. Spacing, radius, elevation
```css
--space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
--space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;

--radius-panel:   24px;
--radius-control: 16px;
--radius-pill:    999px;

--elev-float:
  0 12px 40px rgba(0,0,0,0.45),
  0 2px 8px  rgba(0,0,0,0.30);
```

---

## 6. Glass material (the recipe)
Tasteful translucency — a quiet material, **not** a heavy frosted-white block.

```css
.glass {
  background: var(--glass-fill);
  backdrop-filter: blur(24px) saturate(1.3);
  -webkit-backdrop-filter: blur(24px) saturate(1.3);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--radius-panel);
  box-shadow: var(--elev-float);
  position: relative;
}
/* light catching the top edge — the visionOS detail */
.glass::before {
  content: "";
  position: absolute; inset: 0;
  border-radius: inherit;
  padding-top: 1px;
  background: linear-gradient(180deg, var(--glass-highlight), transparent 40%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  pointer-events: none;
}
```

Rules:
- Glass **requires content behind it to blur** — it always sits over the stage/avatar, never over a flat fill.
- **Max 2–3 glass layers on screen** (`backdrop-filter` is GPU-costly).
- Fill alpha stays low (0.05–0.09). If it looks milky, it's too high.
- No gradients painted *onto* the glass; let it be a neutral material.

---

## 7. Layout
Full-viewport stage; the avatar centered as hero; minimal floating chrome.

```
┌──────────────────────────────────────────────┐
│ signspace                                     │  wordmark · top-left · secondary
│                                               │
│                                               │
│                   ◊ 3D ◊                       │  avatar · centered hero
│                  ╱ avatar ╲                    │  ~55–68% viewport height
│                 ╰─────────╯                    │
│                 ‗‗‗‗‗‗‗‗‗‗‗                    │  soft contact shadow
│                                               │
│             "My name is Jade"                 │  caption · lower third · display
│                                               │
│           ╭───────────────────────╮           │  glass control bar · bottom-center
│           │   ◉      ⟲     1.0×     │          │  mic (primary) · replay · speed
│           ╰───────────────────────╯           │
└──────────────────────────────────────────────┘
```

- **Wordmark:** top-left, `--space-5` inset, `--text-secondary`, → primary on hover.
- **Avatar:** vertically centered, framed on upper body + hands (signing space).
- **Caption:** lower third, centered, max-width ~70ch, never overlaps the avatar's hands.
- **Control bar:** bottom-center, `--space-6` from bottom, glass pill.

**Responsive (mobile):** avatar stays hero, framed slightly tighter; caption scales down via the clamp; control bar widens toward full-width with `--space-4` side insets. Single column always; nothing reflows into the avatar.

---

## 8. 3D stage spec (renderer-agent)
The single most important thing separating "premium" from "cheap Three.js": **tone mapping, anti-aliasing, and color management on; palette matched to the CSS.**

- **Renderer:** `antialias: true`; `toneMapping = ACESFilmicToneMapping`; `toneMappingExposure ≈ 1.0`; `outputColorSpace = SRGBColorSpace`; `pixelRatio = min(devicePixelRatio, 2)`. Transparent canvas so the CSS stage shows through (or paint the same gradient in WebGL — must match §3).
- **Lighting:** soft key (upper-front), gentle fill (opposite, lower), subtle rim/back light for separation from the stage. Add a low-intensity neutral studio IBL/HDRI for soft, non-harsh reflections. No hard speculars.
- **Avatar material:** matte-soft, desaturated neutral (light cool grey); high roughness (~0.8), low metalness. The figure should feel like soft material, not shiny plastic.
- **Floor:** soft contact shadow under the figure (e.g. ContactShadows). Optional faint reflection fade ≤15%. Subtle — grounding, not a feature.
- **Camera:** perspective ~35–40° fov, framed on upper body + hands. **Idle drift:** ±1–2° orbit over a 14–20s loop so the scene is never dead-static. Eased transitions between states.
- **Color-match:** the WebGL background grade and the CSS stage use the same `--bg-stage-*` values so canvas and DOM read as one continuous lit space.

---

## 9. Motion system
Fluid, eased, continuous. Define once, reuse everywhere.

```css
--ease-glass:     cubic-bezier(0.32, 0.72, 0, 1);    /* panel entrances, decelerate */
--ease-soft:      cubic-bezier(0.40, 0.00, 0.20, 1);  /* micro-interactions */
--ease-out-quiet: cubic-bezier(0.22, 1.00, 0.36, 1);  /* caption words */

--dur-micro:   160ms;
--dur-control: 240ms;
--dur-state:   320ms;
--dur-panel:   460ms;
```

| Moment | Treatment |
|--------|-----------|
| Panel / control enter | opacity 0→1 + translateY(10px→0), `--dur-panel` `--ease-glass` |
| Button press | scale 0.97, `--dur-micro` `--ease-soft`; release springs back |
| Button hover | fill → `--glass-fill-hover`, slight brightness lift |
| State change | crossfade, `--dur-state`; **never a hard cut** |
| Listening pulse | accent ring scale+fade loop, **2.4s** `ease-in-out` infinite, low alpha — calm |
| Caption word in | blur(6px)+opacity 0→1 over 280ms `--ease-out-quiet`; outgoing word fades 200ms |
| Focus ring | 2px `--accent`, 2px offset, fades in `--dur-micro` |

**Performance:** animate `transform` and `opacity` only — never width/height/top/left. `will-change` used sparingly. Target 60fps.

**Reduced motion** (`prefers-reduced-motion: reduce`): disable the listening pulse, camera idle drift, and caption blur. Replace with simple opacity fades ≤120ms. Keep the experience legible and calm.

---

## 10. States & copy
Plain, calm, interface-voice copy. No hype, no exclamation, no emoji.

| State | Stage | Control bar | Caption |
|-------|-------|-------------|---------|
| **Idle** | avatar gentle rest motion | mic only | faint prompt: "Tap to speak" |
| **Listening** | calm | mic active, accent pulse ring | "Listening…" (`--text-secondary`) |
| **Processing** | calm | quiet accent sweep on the bar | "Translating…" |
| **Signing** | avatar signs | replay + speed appear | live caption, word-by-word |
| **Error** | calm | mic | `--danger`, actionable: "Didn't catch that — tap to try again." |

Unmatched-vocabulary error (422 from `/api/sign`): "I don't know those signs yet." — never apologize, always give the next action.

---

## 11. Components
- **Wordmark** — `signspace` lowercase, `--text-secondary`. The only branding.
- **Mic control** — circular glass, 60px, the primary action. Active: accent ring + soft `--accent-glow`. Press: scale 0.97. Keyboard: Space/Enter triggers it.
- **Playback** — replay glyph + speed control (0.75× / 1× / 1.0× / 1.25×) as a small glass segment; appears only after a phrase is ready. `tabular-nums` for the speed value.
- **Caption** — lower third, `--font-display`, weight 300, large. Word-by-word crossfade synced to signing.
- **Loader** — while SMPL-X model + assets load: the wordmark breathing, or a single soft dot pulsing. **No spinner.** Calm and on-brand.

---

## 12. Anti-patterns — do NOT ship these
The generic LLM-frontend tells. Forbidden:
- ❌ Purple/indigo gradients, default Tailwind palette, `shadow-lg` on everything.
- ❌ Heavy frosted-white glass blocks; multiple competing accent colors.
- ❌ Pure `#000` background or pure `#fff` text (use the softened tokens).
- ❌ Default-blue buttons, stock pill-with-drop-shadow components.
- ❌ Center-everything with no hierarchy; decorative numbered markers.
- ❌ Emoji in the UI; exclamation marks; "AI magic" hype copy.
- ❌ Bouncy/overshoot springs; animating everything; fast frantic motion.
- ❌ Raw Three.js with no tone mapping / no AA (the cheap-3D look).
- ❌ Animating layout properties (causes jank).
- ❌ Glass placed over a solid fill (nothing to blur → looks like a flat grey box).

---

## 13. Accessibility & quality floor
- Visible keyboard focus on every control (`--accent` ring); full tab order; Space/Enter on mic.
- `prefers-reduced-motion` respected (§9).
- Text contrast meets WCAG AA against the stage (the soft-white tokens pass).
- The caption doubles as access for people reading along — keep it legible and well-timed; it is functional, not just decorative.
- Responsive down to mobile; nothing reflows over the avatar's hands.

---

## 14. Implementation notes
- **Ownership:** `renderer-agent` owns §8 (3D stage) and the avatar canvas; `demo-agent` owns §3–7, §9–13 (glass UI, motion, states, caption).
- **Caption sync:** advance words from the `SMPLXSequence` timing — use `fps` and per-clip `gloss`/`clip_ids` in `meta` to map elapsed frames → current word. The caption and the avatar are driven by the same clock.
- **Perf budget:** ≤3 glass layers; `pixelRatio` capped at 2; transform/opacity-only animation; backdrop-filter only over the stage.
- **Color is shared truth:** §3 tokens are imported by both the CSS and the WebGL background grade. Change them in one place.
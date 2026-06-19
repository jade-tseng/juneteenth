import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { Avatar } from "./avatar.ts";

// The luminous 3D stage (UI.md §8). Tone mapping + AA + color management on,
// palette matched to the CSS tokens, soft three-point light, idle camera drift.
// The avatar is the hero; the canvas is transparent so the CSS stage gradient
// reads through and canvas + DOM are one continuous lit space (§8 color-match).

const css = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)"
).matches;

export class Stage {
  readonly avatar = new Avatar();
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private clock = new THREE.Clock();
  private contact!: THREE.Mesh;
  private baseDist = 2.2; // camera orbit radius, set on resize
  private raf = 0;

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true, // transparent — CSS stage shows through
      powerPreference: "high-performance",
    });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // perspective ~37°, framed on upper body + hands (the signing space)
    this.camera = new THREE.PerspectiveCamera(37, 1, 0.1, 100);
    this.camera.position.set(0, 1.42, 2.2);

    this.scene.add(this.avatar.root);
    this.setupEnvironment();
    this.setupLights();
    this.setupFloor();

    this.resize();
    window.addEventListener("resize", this.resize);
  }

  // soft neutral studio IBL for gentle, non-harsh reflections (§8)
  private setupEnvironment() {
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environment = envTex;
    this.scene.environmentIntensity = 0.45; // soft reflections, not a bright wash
    pmrem.dispose();
  }

  private setupLights() {
    // soft key, upper-front
    const key = new THREE.DirectionalLight(0xfdfbff, 1.35);
    key.position.set(-1.4, 3.2, 2.6);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 8;
    key.shadow.bias = -0.0004;
    key.shadow.radius = 6;
    const c = key.shadow.camera as THREE.OrthographicCamera;
    c.left = -1.5; c.right = 1.5; c.top = 2.6; c.bottom = -0.5;
    this.scene.add(key);

    // gentle fill, opposite + lower, cool
    const fill = new THREE.DirectionalLight(0x9fb0d8, 0.4);
    fill.position.set(2.4, 0.8, 1.6);
    this.scene.add(fill);

    // rim / back light for separation from the stage
    const rim = new THREE.DirectionalLight(0xbcd0ff, 0.85);
    rim.position.set(0.6, 2.4, -3.0);
    this.scene.add(rim);

    // a touch of ambient so shadow cores aren't crushed
    this.scene.add(new THREE.AmbientLight(0x2a3340, 0.45));
  }

  // soft contact shadow grounding the figure (§8). Kept subtle — grounding,
  // not a feature. A baked radial alpha texture stands in for ContactShadows
  // so there is no extra render pass in the loop.
  private setupFloor() {
    const tex = makeRadialShadow();
    const mat = new THREE.MeshBasicMaterial({
      map: tex,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    });
    this.contact = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 1.8), mat);
    this.contact.rotation.x = -Math.PI / 2;
    this.contact.position.y = 0.002;
    this.scene.add(this.contact);
  }

  private resize = () => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.camera.aspect = w / h;
    // frame a little wider on narrow / mobile viewports so hands stay in view
    this.baseDist = THREE.MathUtils.clamp(2.6 * (h / w) ** 0.18, 2.45, 3.3);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  };

  /** onFrame runs every tick with (dt, elapsed) so playback shares this clock. */
  start(onFrame?: (dt: number, elapsed: number) => void) {
    const tick = () => {
      this.raf = requestAnimationFrame(tick);
      const dt = Math.min(this.clock.getDelta(), 0.05);
      const t = this.clock.elapsedTime;

      onFrame?.(dt, t);
      this.avatar.update(dt, t, reducedMotion);

      // idle camera drift — ±1.5° orbit over ~17s so the scene is never dead
      const a = reducedMotion
        ? 0
        : Math.sin(t * ((2 * Math.PI) / 17)) * THREE.MathUtils.degToRad(1.5);
      this.camera.position.set(
        Math.sin(a) * this.baseDist,
        1.42,
        Math.cos(a) * this.baseDist
      );
      this.camera.lookAt(0, 1.32, 0);

      this.renderer.render(this.scene, this.camera);
    };
    tick();
  }

  dispose() {
    cancelAnimationFrame(this.raf);
    window.removeEventListener("resize", this.resize);
    this.renderer.dispose();
  }
}

/** Procedural soft elliptical shadow blob, drawn once to a canvas texture. */
function makeRadialShadow(): THREE.CanvasTexture {
  const size = 256;
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  const ctx = cv.getContext("2d")!;
  const g = ctx.createRadialGradient(
    size / 2, size / 2, 0,
    size / 2, size / 2, size / 2
  );
  g.addColorStop(0, "rgba(0,0,0,0.9)");
  g.addColorStop(0.5, "rgba(0,0,0,0.35)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

// re-export so callers can read the same flag the stage uses
export { reducedMotion };
// keep the css() helper available for future shared-token reads from WebGL
void css;

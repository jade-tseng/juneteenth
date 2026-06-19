import * as THREE from "three";
import type { GestureCue } from "./types.ts";

// Placeholder articulated figure. This is deliberately NOT SMPL-X — it is
// honest scaffolding so the stage, caption clock, and state machine can be
// built and demoed now. renderer-agent's Route A forward pass (template verts +
// blendshapes + LBS driving a BufferGeometry from SMPLXFrame) replaces the
// rig built here; the public API (applyGesture / settleToRest / update) is what
// the rest of the app depends on, and maps cleanly onto a frame-driven mesh.

type JointName =
  | "spine"
  | "head"
  | "shoulderL"
  | "shoulderR"
  | "elbowL"
  | "elbowR"
  | "wristL"
  | "wristR";

type Euler3 = [number, number, number];
type Pose = Partial<Record<JointName, Euler3>>;

// Arms hang at rest with a soft natural bend. Everything eases back to this.
const REST: Record<JointName, Euler3> = {
  spine: [0, 0, 0],
  head: [0, 0, 0],
  shoulderL: [0, 0, 0.09],
  shoulderR: [0, 0, -0.09],
  elbowL: [0.22, 0, 0],
  elbowR: [0.22, 0, 0],
  wristL: [0, 0, 0],
  wristR: [0, 0, 0],
};

// Target arm placements per gesture. Read qualitatively: hands come into the
// signing space in front of the chest/face. Pitch (x) raises the arm forward;
// elbow x bends it. Dynamic detail (waggle, alternation) is layered in update().
const POSES: Partial<Record<GestureCue, Pose>> = {
  rest: {},
  wave: { shoulderR: [-1.35, 0, -0.2], elbowR: [1.5, 0, 0] },
  "point-out": { shoulderR: [-1.05, 0, -0.15], elbowR: [0.32, 0, 0] },
  "point-self": { shoulderR: [-0.72, 0, 0.35], elbowR: [1.75, 0, 0] },
  "two-hands-up": {
    shoulderL: [-0.55, 0, 0.25],
    shoulderR: [-0.55, 0, -0.25],
    elbowL: [1.4, 0, 0],
    elbowR: [1.4, 0, 0],
  },
  "tap-down": {
    shoulderL: [-0.62, 0, 0.18],
    shoulderR: [-0.62, 0, -0.18],
    elbowL: [1.2, 0, 0],
    elbowR: [1.2, 0, 0],
  },
  "name-tap": {
    shoulderL: [-0.5, 0, 0.22],
    shoulderR: [-0.5, 0, -0.22],
    elbowL: [1.55, 0, 0],
    elbowR: [1.55, 0, 0],
  },
  "sign-sweep": {
    shoulderL: [-0.7, 0, 0.3],
    shoulderR: [-0.7, 0, -0.3],
    elbowL: [1.05, 0, 0],
    elbowR: [1.05, 0, 0],
  },
  but: {
    shoulderL: [-0.5, 0, 0.4],
    shoulderR: [-0.5, 0, -0.4],
    elbowL: [1.0, 0, 0.2],
    elbowR: [1.0, 0, -0.2],
  },
  can: {
    shoulderL: [-0.42, 0, 0.2],
    shoulderR: [-0.42, 0, -0.2],
    elbowL: [1.0, 0, 0],
    elbowR: [1.0, 0, 0],
  },
  happy: {
    shoulderL: [-0.6, 0, 0.28],
    shoulderR: [-0.6, 0, -0.28],
    elbowL: [1.45, 0, 0],
    elbowR: [1.45, 0, 0],
  },
  communicate: {
    shoulderL: [-0.85, 0, 0.2],
    shoulderR: [-0.85, 0, -0.2],
    elbowL: [1.6, 0, 0],
    elbowR: [1.6, 0, 0],
  },
  fingerspell: { shoulderR: [-0.8, 0, -0.1], elbowR: [1.75, 0, 0] },
};

const MATTE = (color: number) =>
  new THREE.MeshStandardMaterial({
    color,
    roughness: 0.85,
    metalness: 0.04,
    envMapIntensity: 0.3,
  });

export class Avatar {
  readonly root = new THREE.Group();
  private joints = {} as Record<JointName, THREE.Group>;
  private targets = {} as Record<JointName, THREE.Quaternion>;
  private current: GestureCue = "rest";
  private gestureTime = 0;
  private skin = MATTE(0x8b95a6); // desaturated cool grey, matte (§8)

  constructor() {
    this.build();
    this.setPose("rest");
    // initialise live quaternions to their targets so frame 1 isn't a snap
    for (const name of Object.keys(this.joints) as JointName[]) {
      this.joints[name].quaternion.copy(this.targets[name]);
    }
  }

  // ── rig construction ──────────────────────────────────────────────────
  private joint(name: JointName, parent: THREE.Object3D, pos: THREE.Vector3) {
    const g = new THREE.Group();
    g.position.copy(pos);
    parent.add(g);
    this.joints[name] = g;
    this.targets[name] = new THREE.Quaternion();
    return g;
  }

  private limb(parent: THREE.Object3D, length: number, radius: number) {
    // capsule extends downward from the pivot it is parented to
    const geo = new THREE.CapsuleGeometry(radius, length - radius * 2, 6, 16);
    const mesh = new THREE.Mesh(geo, this.skin);
    mesh.position.y = -length / 2;
    mesh.castShadow = true;
    parent.add(mesh);
    return mesh;
  }

  private build() {
    // The figure stands with feet at y=0; chest/hands sit in the framed zone.
    const hips = new THREE.Group();
    hips.position.y = 0.92;
    this.root.add(hips);

    // legs (static — keep the figure grounded for the contact shadow)
    for (const side of [-1, 1]) {
      const hip = new THREE.Group();
      hip.position.set(0.1 * side, 0, 0);
      hips.add(hip);
      const thigh = this.limb(hip, 0.46, 0.085);
      const knee = new THREE.Group();
      knee.position.y = -0.46;
      thigh.parent!.add(knee);
      this.limb(knee, 0.44, 0.07);
    }
    const pelvis = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.15, 0.12, 6, 16),
      this.skin
    );
    pelvis.castShadow = true;
    hips.add(pelvis);

    // spine → chest
    const spine = this.joint("spine", hips, new THREE.Vector3(0, 0.06, 0));
    const torso = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.17, 0.34, 8, 20),
      this.skin
    );
    torso.position.y = 0.27;
    torso.scale.z = 0.72; // flatten front-to-back so it reads as a torso
    torso.castShadow = true;
    spine.add(torso);

    const chest = new THREE.Group();
    chest.position.y = 0.5;
    spine.add(chest);

    // neck → head
    const head = this.joint("head", chest, new THREE.Vector3(0, 0.08, 0));
    const neck = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.05, 0.06, 6, 12),
      this.skin
    );
    neck.position.y = 0.04;
    head.add(neck);
    const skull = new THREE.Mesh(
      new THREE.SphereGeometry(0.115, 28, 28),
      this.skin
    );
    skull.position.y = 0.18;
    skull.scale.set(0.92, 1.05, 0.95);
    skull.castShadow = true;
    head.add(skull);

    // arms: shoulder → elbow → wrist → hand, per side
    for (const s of ["L", "R"] as const) {
      const x = 0.2 * (s === "L" ? 1 : -1);
      const shoulder = this.joint(
        `shoulder${s}` as JointName,
        chest,
        new THREE.Vector3(x, 0.02, 0)
      );
      const upper = this.limb(shoulder, 0.28, 0.058);

      const elbow = this.joint(
        `elbow${s}` as JointName,
        upper.parent!,
        new THREE.Vector3(0, -0.28, 0)
      );
      const fore = this.limb(elbow, 0.26, 0.05);

      const wrist = this.joint(
        `wrist${s}` as JointName,
        fore.parent!,
        new THREE.Vector3(0, -0.26, 0)
      );
      // hand: palm + a suggestion of fingers (ASL lives here — keep it present
      // even in the placeholder so motion in the signing space reads)
      const palm = new THREE.Mesh(
        new THREE.BoxGeometry(0.085, 0.11, 0.035),
        this.skin
      );
      palm.position.y = -0.07;
      palm.castShadow = true;
      wrist.add(palm);
      for (let f = 0; f < 4; f++) {
        const finger = new THREE.Mesh(
          new THREE.CapsuleGeometry(0.011, 0.05, 4, 8),
          this.skin
        );
        finger.position.set(-0.03 + f * 0.02, -0.15, 0);
        finger.castShadow = true;
        wrist.add(finger);
      }
      const thumb = new THREE.Mesh(
        new THREE.CapsuleGeometry(0.013, 0.04, 4, 8),
        this.skin
      );
      thumb.position.set(0.05 * (s === "L" ? -1 : 1), -0.08, 0.01);
      thumb.rotation.z = 0.8 * (s === "L" ? 1 : -1);
      wrist.add(thumb);
    }
  }

  // ── posing ────────────────────────────────────────────────────────────
  private setPose(cue: GestureCue) {
    const pose = POSES[cue] ?? {};
    const e = new THREE.Euler();
    for (const name of Object.keys(this.joints) as JointName[]) {
      const [x, y, z] = pose[name] ?? REST[name];
      e.set(x, y, z, "XYZ");
      this.targets[name].setFromEuler(e);
    }
  }

  /** Begin a gesture; the rig eases toward it over the following frames. */
  applyGesture(cue: GestureCue) {
    this.current = cue;
    this.gestureTime = 0;
    this.setPose(cue);
  }

  /** Return to a calm resting posture (idle / end of phrase). */
  settleToRest() {
    this.applyGesture("rest");
  }

  // ── per-frame update ────────────────────────────────────────────────────
  private tmp = new THREE.Quaternion();
  private tmpE = new THREE.Euler();

  update(dt: number, elapsed: number, reducedMotion: boolean) {
    this.gestureTime += dt;

    // Dynamic detail layered on the static target for lively gestures.
    const overlay = this.gestureOverlay(this.gestureTime, reducedMotion);

    // gentle idle breathing on the spine/head, always present so it's not dead
    const breath = reducedMotion ? 0 : Math.sin(elapsed * 0.9) * 0.012;
    this.tmpE.set(breath, Math.sin(elapsed * 0.3) * 0.02, 0, "XYZ");
    const spineTarget = this.tmp.setFromEuler(this.tmpE).premultiply(
      this.targets.spine
    );
    this.damp(this.joints.spine.quaternion, spineTarget, 6, dt);

    // ease every joint toward target (+overlay for the active hands)
    for (const name of Object.keys(this.joints) as JointName[]) {
      if (name === "spine") continue;
      let target = this.targets[name];
      const o = overlay[name];
      if (o) {
        this.tmpE.set(o[0], o[1], o[2], "XYZ");
        target = this.tmp.setFromEuler(this.tmpE).premultiply(this.targets[name]);
      }
      // slerp-style ease — never lerp raw angles (mirrors the W4 blend ethos)
      this.damp(this.joints[name].quaternion, target, 7, dt);
    }
  }

  /** Quaternion critical-damp toward target: framerate-independent slerp. */
  private damp(q: THREE.Quaternion, target: THREE.Quaternion, k: number, dt: number) {
    const t = 1 - Math.exp(-k * dt);
    q.slerp(target, t);
  }

  /** Small additive euler offsets that give a gesture life over time. */
  private gestureOverlay(t: number, reduced: boolean): Partial<Record<JointName, Euler3>> {
    if (reduced) return {};
    const wag = Math.sin(t * 9) * 0.28;
    const slow = Math.sin(t * 4.5) * 0.18;
    const alt = Math.sin(t * 5) * 0.22;
    switch (this.current) {
      case "wave":
        return { wristR: [0, 0, wag] };
      case "fingerspell":
        return { wristR: [wag * 0.7, wag, 0] };
      case "sign-sweep":
        return { shoulderL: [slow, 0, 0], shoulderR: [slow, 0, 0] };
      case "happy":
        return { shoulderL: [slow, 0, 0], shoulderR: [slow, 0, 0] };
      case "communicate":
        return { elbowL: [alt, 0, 0], elbowR: [-alt, 0, 0] };
      case "name-tap":
        return { elbowL: [Math.abs(slow), 0, 0], elbowR: [Math.abs(slow), 0, 0] };
      case "but":
        return { wristL: [0, slow, 0], wristR: [0, -slow, 0] };
      default:
        return {};
    }
  }
}

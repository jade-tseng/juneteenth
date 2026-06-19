import * as THREE from "three";
import type { SMPLXModel } from "./model.ts";
import { SMPLXForward } from "./forward.ts";
import type { SMPLXFrame } from "../types.ts";

// SMPL-X mesh (Route A, CLAUDE.md §4.5). Builds a Three.js BufferGeometry from
// the model faces + an initial forward-pass and exposes setFrame()/setRest() so
// the player drives it from a SMPLXSequence. Material matches the matte,
// desaturated look of the placeholder avatar (UI.md §8) for visual continuity.
//
// The SMPL-X canonical frame is Y-up with the figure facing +Z; the placeholder
// avatar stands feet-at-y=0, so we lift the mesh to roughly the same framed zone
// the camera (stage.ts) expects. A single root group carries that transform.

const MATTE = (color: number) =>
  new THREE.MeshStandardMaterial({
    color,
    roughness: 0.85,
    metalness: 0.04,
    envMapIntensity: 0.3,
    flatShading: false,
  });

export class SMPLXMesh {
  /** Add this to the scene; mirrors Avatar.root so stage.ts can swap cleanly. */
  readonly root = new THREE.Group();

  private fwd: SMPLXForward;
  private geometry: THREE.BufferGeometry;
  private position: THREE.BufferAttribute;
  private mesh: THREE.Mesh;

  constructor(model: SMPLXModel) {
    this.fwd = new SMPLXForward(model);

    // initial vertices = rest pose
    const verts = this.fwd.computeRest();

    this.geometry = new THREE.BufferGeometry();
    // copy so the geometry owns its buffer (the forward pass reuses its own)
    this.position = new THREE.BufferAttribute(new Float32Array(verts), 3);
    this.position.setUsage(THREE.DynamicDrawUsage);
    this.geometry.setAttribute("position", this.position);
    this.geometry.setIndex(new THREE.BufferAttribute(model.faces, 1));
    this.geometry.computeVertexNormals();

    this.mesh = new THREE.Mesh(this.geometry, MATTE(0x8b95a6));
    this.mesh.castShadow = true;
    this.mesh.receiveShadow = false;
    this.mesh.frustumCulled = false; // we rewrite positions every frame

    this.root.add(this.mesh);

    // SMPL-X is pelvis-centered (feet at ~y=-1.1); the stage camera expects a
    // figure standing on the floor (feet at y=0, looking at y≈1.32). Lift the
    // rest mesh so its lowest point sits on the ground. Computed once from the
    // rest pose so the avatar doesn't bob frame-to-frame.
    this.geometry.computeBoundingBox();
    const minY = this.geometry.boundingBox?.min.y ?? 0;
    this.root.position.y = -minY;
  }

  /** Bind the sequence's constant betas before playback (shape is per-seq). */
  bindBetas(betas: number[]): void {
    this.fwd.bindBetas(betas);
  }

  /** Run the forward pass for a frame and push the result into the geometry. */
  setFrame(frame: SMPLXFrame): void {
    const verts = this.fwd.compute(frame);
    this.updateGeometry(verts);
  }

  /** Idle / neutral rest pose. */
  setRest(): void {
    const verts = this.fwd.computeRest();
    this.updateGeometry(verts);
  }

  private updateGeometry(verts: Float32Array): void {
    (this.position.array as Float32Array).set(verts);
    this.position.needsUpdate = true;
    this.geometry.computeVertexNormals();
    this.geometry.computeBoundingSphere();
  }

  dispose(): void {
    this.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
  }
}

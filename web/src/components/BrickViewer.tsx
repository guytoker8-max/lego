/**
 * The 3D preview: the structured model itself, drawn brick by brick.
 *
 * Every box here is one element from the parts list, at its real size and
 * position, with a stud for every stud it has. Nothing is a mesh that merely
 * resembles bricks, which is the point: what the customer turns around on
 * screen is the same object the parts list counts, the price is computed
 * from and the supplier packs.
 *
 * Instanced meshes keep it to a handful of draw calls however many pieces
 * there are, so a 3,000-piece set still turns smoothly on a phone.
 *
 * For the instructions, `step` limits the drawing to the bricks placed up
 * to that step and fades everything placed earlier, so the new pieces stand
 * out exactly as they do in the printed booklet.
 */

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

import type { Geometry } from '../api';

const STUD = 8; // mm
const PLATE = 3.2; // mm
const GAP = 0.18; // mm shaved off each side so seams read between bricks

interface Props {
  geometry: Geometry;
  step?: number | null; // 1-based; null or undefined shows the finished model
  autoRotate?: boolean;
  interactive?: boolean;
  background?: string | null; // null: transparent
  className?: string;
  onReady?: () => void;
}

export default function BrickViewer({
  geometry,
  step = null,
  autoRotate = false,
  interactive = true,
  background = null,
  className,
  onReady,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    apply: (step: number | null) => void;
    dispose: () => void;
    setAutoRotate: (on: boolean) => void;
  } | null>(null);
  const [failed, setFailed] = useState(false);

  // Build the scene once per model.
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: background === null, preserveDrawingBuffer: true });
    } catch {
      setFailed(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    // Neutral keeps brick colours true to the palette; ACES washes them out.
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    if (background) scene.background = new THREE.Color(background);
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.45;

    // ---- bricks, in build order ---------------------------------------
    const order: number[] = [];
    const seen = new Set<number>();
    geometry.steps.forEach((s) => s.forEach((i) => { if (!seen.has(i)) { seen.add(i); order.push(i); } }));
    geometry.bricks.forEach((_, i) => { if (!seen.has(i)) order.push(i); });
    const stepEnds: number[] = [];
    let running = 0;
    geometry.steps.forEach((s) => { running += s.length; stepEnds.push(running); });

    const [sx, sy, sz] = geometry.size_studs;
    const cx = (sx * STUD) / 2;
    const cz = (sz * STUD) / 2;
    const height = sy * PLATE;

    const bodyGeo = new THREE.BoxGeometry(1, 1, 1);
    const studGeo = new THREE.CylinderGeometry(2.4, 2.4, 1.7, 16);
    const mat = new THREE.MeshStandardMaterial({ roughness: 0.32, metalness: 0.0 });
    const studMat = new THREE.MeshStandardMaterial({ roughness: 0.3, metalness: 0.0 });

    let studCount = 0;
    order.forEach((i) => {
      const [pid] = geometry.bricks[i];
      const p = geometry.parts[pid];
      if (p?.has_studs) studCount += p.w * p.d;
    });

    const bodies = new THREE.InstancedMesh(bodyGeo, mat, Math.max(1, order.length));
    const studs = new THREE.InstancedMesh(studGeo, studMat, Math.max(1, studCount));
    bodies.castShadow = bodies.receiveShadow = true;
    studs.castShadow = true;

    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const baseColors: THREE.Color[] = [];
    const studOwner: number[] = []; // stud instance -> position in `order`
    let si = 0;
    order.forEach((brickIndex, k) => {
      const [pid, cid, x, y, z, rot] = geometry.bricks[brickIndex];
      const p = geometry.parts[pid] ?? { w: 1, d: 1, h: 3, has_studs: true };
      const [w, d] = rot % 180 === 90 ? [p.d, p.w] : [p.w, p.d];
      const px = x * STUD + (w * STUD) / 2 - cx;
      const py = y * PLATE + (p.h * PLATE) / 2;
      const pz = z * STUD + (d * STUD) / 2 - cz;
      m.compose(
        new THREE.Vector3(px, py, pz),
        q,
        new THREE.Vector3(w * STUD - GAP * 2, p.h * PLATE - GAP, d * STUD - GAP * 2),
      );
      bodies.setMatrixAt(k, m);
      const color = new THREE.Color(geometry.palette[String(cid)]?.hex ?? '#999999');
      baseColors.push(color);
      bodies.setColorAt(k, color);
      if (p.has_studs) {
        for (let dz = 0; dz < d; dz++) {
          for (let dx = 0; dx < w; dx++) {
            m.makeTranslation(
              x * STUD + (dx + 0.5) * STUD - cx,
              y * PLATE + p.h * PLATE + 0.85,
              z * STUD + (dz + 0.5) * STUD - cz,
            );
            studs.setMatrixAt(si, m);
            studs.setColorAt(si, color);
            studOwner.push(k);
            si++;
          }
        }
      }
    });
    scene.add(bodies, studs);

    // ---- light, ground, camera ----------------------------------------
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd9d2c5, 0.45));
    const sun = new THREE.DirectionalLight(0xffffff, 1.5);
    const span = Math.max(sx * STUD, sz * STUD, height);
    sun.position.set(span * 0.8, span * 1.6, span * 1.1);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    const sc = sun.shadow.camera as THREE.OrthographicCamera;
    sc.left = sc.bottom = -span;
    sc.right = sc.top = span;
    sc.near = 1;
    sc.far = span * 5;
    sun.shadow.bias = -0.0005;
    sun.shadow.radius = 6;
    scene.add(sun);

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(span * 8, span * 8),
      new THREE.ShadowMaterial({ opacity: 0.16 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const camera = new THREE.PerspectiveCamera(32, 1, 1, span * 20);
    const target = new THREE.Vector3(0, height * 0.45, 0);
    const dist = span * 2.3;
    // A three-quarter view that favours the front, which is the side the
    // photo showed.
    camera.position.set(dist * 0.48, height * 0.5 + dist * 0.34, dist * 0.86);
    camera.lookAt(target);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(target);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.minDistance = span * 0.9;
    controls.maxDistance = span * 5;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 1.1;
    controls.enabled = interactive;
    // Let the page scroll on touch devices unless the finger is clearly
    // turning the model: one finger rotates, the page still scrolls with two.
    renderer.domElement.style.touchAction = interactive ? 'pan-y' : 'auto';

    // ---- step display ---------------------------------------------------
    let dirty = true;
    const fadeTo = new THREE.Color(background ?? '#f4efe6');
    const apply = (s: number | null) => {
      const visible = s === null || s <= 0 || s > stepEnds.length ? order.length : stepEnds[s - 1];
      const newFrom = s === null || s <= 1 || s > stepEnds.length ? 0 : stepEnds[s - 2];
      bodies.count = visible;
      const tmp = new THREE.Color();
      for (let k = 0; k < order.length; k++) {
        tmp.copy(baseColors[k]);
        if (s !== null && k < newFrom) tmp.lerp(fadeTo, 0.55);
        bodies.setColorAt(k, tmp);
      }
      let visibleStuds = 0;
      for (let j = 0; j < studOwner.length; j++) {
        const k = studOwner[j];
        if (k < visible) visibleStuds = j + 1;
        tmp.copy(baseColors[k]);
        if (s !== null && k < newFrom) tmp.lerp(fadeTo, 0.55);
        studs.setColorAt(j, tmp);
      }
      studs.count = visibleStuds;
      if (bodies.instanceColor) bodies.instanceColor.needsUpdate = true;
      if (studs.instanceColor) studs.instanceColor.needsUpdate = true;
      dirty = true;
    };
    apply(step);

    // ---- sizing and the loop -------------------------------------------
    const resize = () => {
      const w = el.clientWidth || 1;
      const h = el.clientHeight || 1;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = '100%';
      renderer.domElement.style.height = '100%';
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      dirty = true;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    let frame = 0;
    let running2 = true;
    let first = true;
    // Draw only when something changed: the camera moved (dragging, damping,
    // auto-rotation), the step changed, or the canvas was resized. A still
    // model costs nothing, which matters on a phone's battery.
    const loop = () => {
      if (!running2) return;
      const moved = controls.update();
      if (moved || dirty || first) {
        renderer.render(scene, camera);
        dirty = false;
      }
      if (first) {
        first = false;
        onReady?.();
      }
      frame = requestAnimationFrame(loop);
    };
    // Pause when off screen: a landing page with a turning model should not
    // keep a phone's GPU busy while the reader is further down.
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !running2) {
        running2 = true;
        loop();
      } else if (!entry.isIntersecting && running2) {
        running2 = false;
        cancelAnimationFrame(frame);
      }
    });
    io.observe(el);
    loop();

    sceneRef.current = {
      apply,
      setAutoRotate: (on) => { controls.autoRotate = on; },
      dispose: () => {
        running2 = false;
        cancelAnimationFrame(frame);
        io.disconnect();
        ro.disconnect();
        controls.dispose();
        bodyGeo.dispose();
        studGeo.dispose();
        mat.dispose();
        studMat.dispose();
        pmrem.dispose();
        renderer.dispose();
        renderer.domElement.remove();
      },
    };
    return () => {
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geometry, background, interactive]);

  useEffect(() => {
    sceneRef.current?.apply(step);
  }, [step]);

  useEffect(() => {
    sceneRef.current?.setAutoRotate(autoRotate);
  }, [autoRotate]);

  if (failed) {
    return (
      <div className={`viewer viewer--fallback ${className ?? ''}`}>
        <p>Your browser can't show 3D here, but your set is ready below.</p>
      </div>
    );
  }
  return <div ref={host} className={`viewer ${className ?? ''}`} />;
}

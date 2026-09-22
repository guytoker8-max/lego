/**
 * The 3D view of the model.
 *
 * It draws the elements themselves -- one box per brick, at its real size and
 * position, with a stud on top of every stud it has -- rather than a mesh
 * that resembles bricks. That matters beyond looks: what you rotate here is
 * the same structure the parts list counts and the booklet builds, so if the
 * model were wrong you would see it.
 *
 * Drawn with instanced meshes, two draw calls for the whole model no matter
 * how many pieces, because a thousand separate meshes will not hold 60fps on
 * a phone. Colour is per instance, so the palette costs nothing extra.
 *
 * `visibleCount` is what the instructions screen drives: pass the number of
 * elements placed so far and the rest simply are not drawn, so stepping
 * through the booklet builds the model in front of you.
 */

import React, { useCallback, useEffect, useRef } from 'react';
import { PanResponder, StyleSheet, View } from 'react-native';
import { GLView } from 'expo-gl';
import * as THREE from 'three';
import { Renderer } from 'expo-three';

import type { Geometry } from '@/api/client';

const STUD = 8;          // mm, matches the server's grid
const PLATE = 3.2;       // mm

export type ViewAngle = 'front' | 'back' | 'side' | 'left' | 'right' | 'top' | 'free';

const ANGLES: Record<Exclude<ViewAngle, 'free'>, [number, number]> = {
  // [azimuth, elevation] in radians
  front: [0, 0.18],
  back: [Math.PI, 0.18],
  side: [Math.PI / 2, 0.18],
  left: [-Math.PI / 2, 0.18],
  right: [Math.PI / 2, 0.18],
  top: [0, Math.PI / 2 - 0.05],
};

type Props = {
  geometry: Geometry;
  visibleCount?: number;
  highlightFrom?: number;      // elements at or after this index glow
  angle?: ViewAngle;
  style?: any;
  interactive?: boolean;
};

export default function BrickViewer({
  geometry,
  visibleCount,
  highlightFrom,
  angle = 'free',
  style,
  interactive = true,
}: Props) {
  const state = useRef({
    azimuth: 0.7,
    elevation: 0.35,
    distance: 1.0,
    panX: 0,
    panY: 0,
    dirty: true,
  }).current;

  const scene = useRef<{
    bricks?: THREE.InstancedMesh;
    studs?: THREE.InstancedMesh;
    camera?: THREE.PerspectiveCamera;
    group?: THREE.Group;
    radius: number;
    centre: THREE.Vector3;
  }>({ radius: 100, centre: new THREE.Vector3() }).current;

  // ---- gestures ----------------------------------------------------------

  const gesture = useRef({ x: 0, y: 0, dist: 0 }).current;

  const responder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => interactive,
      onMoveShouldSetPanResponder: () => interactive,
      onPanResponderGrant: (e) => {
        gesture.x = e.nativeEvent.pageX;
        gesture.y = e.nativeEvent.pageY;
        gesture.dist = 0;
      },
      onPanResponderMove: (e, g) => {
        const touches = e.nativeEvent.touches;
        if (touches.length >= 2) {
          // Two fingers: pinch to zoom, drag to pan.
          const [a, b] = touches;
          const d = Math.hypot(a.pageX - b.pageX, a.pageY - b.pageY);
          if (gesture.dist > 0) {
            state.distance *= gesture.dist / d;
            state.distance = Math.min(3.0, Math.max(0.35, state.distance));
          }
          gesture.dist = d;
          state.panX += g.dx * 0.0016;
          state.panY += g.dy * 0.0016;
        } else {
          gesture.dist = 0;
          state.azimuth -= g.dx * 0.008;
          state.elevation += g.dy * 0.008;
          const limit = Math.PI / 2 - 0.05;
          state.elevation = Math.min(limit, Math.max(-limit, state.elevation));
        }
        state.dirty = true;
      },
      onPanResponderRelease: () => {
        gesture.dist = 0;
      },
    }),
  ).current;

  // ---- preset angles -----------------------------------------------------

  useEffect(() => {
    if (angle === 'free') return;
    const [az, el] = ANGLES[angle];
    state.azimuth = az;
    state.elevation = el;
    state.panX = 0;
    state.panY = 0;
    state.dirty = true;
  }, [angle, state]);

  // ---- how much of the model is built -----------------------------------

  useEffect(() => {
    const mesh = scene.bricks;
    const studs = scene.studs;
    if (!mesh) return;
    const total = geometry.bricks.length;
    const shown = visibleCount == null ? total : Math.max(0, Math.min(total, visibleCount));
    mesh.count = shown;
    if (studs) {
      // Studs are indexed separately; keep them in step with the bricks.
      studs.count = studCountFor(geometry, shown);
    }
    applyHighlight(scene, geometry, highlightFrom, shown);
    state.dirty = true;
  }, [visibleCount, highlightFrom, geometry, scene, state]);

  // ---- the scene ---------------------------------------------------------

  const onContextCreate = useCallback(
    async (gl: any) => {
      // expo-three's Renderer *is* a WebGLRenderer at runtime; its published
      // types omit the inherited surface, so it is narrowed back here rather
      // than every call site being cast.
      const renderer = new Renderer({ gl }) as unknown as THREE.WebGLRenderer;
      const width = gl.drawingBufferWidth;
      const height = gl.drawingBufferHeight;
      renderer.setSize(width, height);
      renderer.setClearColor(0xf3f0ea, 1);

      const three = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(38, width / height, 1, 12000);
      scene.camera = camera;

      // Light from above and slightly to the side reads studs as round; a
      // dim fill from the other side keeps the shadowed faces from going
      // black, which is what makes dark bricks disappear on a phone screen.
      three.add(new THREE.AmbientLight(0xffffff, 0.62));
      const key = new THREE.DirectionalLight(0xffffff, 0.85);
      key.position.set(0.5, 1.0, 0.7);
      three.add(key);
      const fill = new THREE.DirectionalLight(0xffffff, 0.3);
      fill.position.set(-0.7, 0.2, -0.5);
      three.add(fill);

      const group = new THREE.Group();
      three.add(group);
      scene.group = group;

      build(geometry, group, scene);

      const renderFrame = () => {
        requestAnimationFrame(renderFrame);
        if (state.dirty) {
          position(camera, scene, state);
          state.dirty = false;
        }
        renderer.render(three, camera);
        gl.endFrameEXP();
      };
      state.dirty = true;
      renderFrame();
    },
    [geometry, scene, state],
  );

  return (
    <View style={[styles.wrap, style]} {...(interactive ? responder.panHandlers : {})}>
      <GLView style={StyleSheet.absoluteFill} onContextCreate={onContextCreate} />
    </View>
  );
}

// ---------------------------------------------------------------------------
// scene construction
// ---------------------------------------------------------------------------

function build(geometry: Geometry, group: THREE.Group, scene: any) {
  const { bricks, parts, palette } = geometry;

  const brickGeo = new THREE.BoxGeometry(1, 1, 1);
  const studGeo = new THREE.CylinderGeometry(0.30, 0.30, 0.18, 12);
  const material = new THREE.MeshLambertMaterial({ vertexColors: true });
  const studMaterial = new THREE.MeshLambertMaterial({ vertexColors: true });

  const totalStuds = studCountFor(geometry, bricks.length);

  const brickMesh = new THREE.InstancedMesh(brickGeo, material, bricks.length || 1);
  const studMesh = new THREE.InstancedMesh(studGeo, studMaterial, totalStuds || 1);
  brickMesh.instanceColor = new THREE.InstancedBufferAttribute(
    new Float32Array(Math.max(1, bricks.length) * 3), 3);
  studMesh.instanceColor = new THREE.InstancedBufferAttribute(
    new Float32Array(Math.max(1, totalStuds) * 3), 3);

  const m = new THREE.Matrix4();
  const colour = new THREE.Color();
  const min = new THREE.Vector3(Infinity, Infinity, Infinity);
  const max = new THREE.Vector3(-Infinity, -Infinity, -Infinity);

  let studIndex = 0;

  bricks.forEach(([partId, colorId, x, y, z, rotation], i) => {
    const part = parts[partId];
    if (!part) return;
    const rotated = rotation % 180 === 90;
    const w = rotated ? part.d : part.w;
    const d = rotated ? part.w : part.d;

    const sizeX = w * STUD;
    const sizeY = part.h * PLATE;
    const sizeZ = d * STUD;
    const cx = (x + w / 2) * STUD;
    const cy = y * PLATE + sizeY / 2;
    const cz = (z + d / 2) * STUD;

    // A hair under full size, so neighbouring bricks show a seam. Without it
    // a wall of one colour renders as a single flat slab and the model stops
    // reading as something built out of parts.
    m.makeScale(sizeX * 0.985, sizeY * 0.97, sizeZ * 0.985);
    m.setPosition(cx, cy, cz);
    brickMesh.setMatrixAt(i, m);

    const hex = palette[String(colorId)]?.hex ?? '#CCCCCC';
    colour.set(hex);
    brickMesh.setColorAt(i, colour);

    min.min(new THREE.Vector3(cx - sizeX / 2, cy - sizeY / 2, cz - sizeZ / 2));
    max.max(new THREE.Vector3(cx + sizeX / 2, cy + sizeY / 2, cz + sizeZ / 2));

    if (part.has_studs) {
      for (let dx = 0; dx < w; dx += 1) {
        for (let dz = 0; dz < d; dz += 1) {
          m.makeScale(STUD, PLATE * 1.4, STUD);
          m.setPosition(
            (x + dx + 0.5) * STUD,
            y * PLATE + sizeY + PLATE * 0.24,
            (z + dz + 0.5) * STUD,
          );
          studMesh.setMatrixAt(studIndex, m);
          studMesh.setColorAt(studIndex, colour);
          studIndex += 1;
        }
      }
    }
  });

  brickMesh.instanceMatrix.needsUpdate = true;
  studMesh.instanceMatrix.needsUpdate = true;
  if (brickMesh.instanceColor) brickMesh.instanceColor.needsUpdate = true;
  if (studMesh.instanceColor) studMesh.instanceColor.needsUpdate = true;

  group.add(brickMesh);
  group.add(studMesh);
  scene.bricks = brickMesh;
  scene.studs = studMesh;
  scene.baseColors = (brickMesh.instanceColor!.array as Float32Array).slice();

  const centre = new THREE.Vector3().addVectors(min, max).multiplyScalar(0.5);
  scene.centre = centre;
  scene.radius = Math.max(20, min.distanceTo(max) / 2);
}

/** Studs belonging to the first `count` bricks, in the same order. */
function studCountFor(geometry: Geometry, count: number): number {
  let n = 0;
  for (let i = 0; i < count; i += 1) {
    const [partId, , , , , rotation] = geometry.bricks[i];
    const part = geometry.parts[partId];
    if (!part || !part.has_studs) continue;
    n += part.w * part.d;
  }
  return n;
}

/** Dim everything placed earlier so this step's pieces stand out. */
function applyHighlight(
  scene: any, geometry: Geometry, from: number | undefined, shown: number,
) {
  const mesh = scene.bricks as THREE.InstancedMesh | undefined;
  if (!mesh || !mesh.instanceColor || !scene.baseColors) return;
  const arr = mesh.instanceColor.array as Float32Array;
  const base = scene.baseColors as Float32Array;
  for (let i = 0; i < shown; i += 1) {
    const dim = from != null && i < from;
    for (let c = 0; c < 3; c += 1) {
      const v = base[i * 3 + c];
      // Fade toward the background rather than toward black: a dimmed dark
      // brick has to stay visible, or the model looks like it has holes.
      arr[i * 3 + c] = dim ? v * 0.45 + 0.42 : v;
    }
  }
  mesh.instanceColor.needsUpdate = true;
}

function position(camera: THREE.PerspectiveCamera, scene: any, state: any) {
  const r = scene.radius * 2.35 * state.distance;
  const { azimuth, elevation } = state;
  const target = scene.centre.clone();
  target.x += state.panX * scene.radius * 2;
  target.y -= state.panY * scene.radius * 2;

  camera.position.set(
    target.x + r * Math.cos(elevation) * Math.sin(azimuth),
    target.y + r * Math.sin(elevation),
    target.z + r * Math.cos(elevation) * Math.cos(azimuth),
  );
  camera.lookAt(target);
  camera.updateProjectionMatrix();
}

const styles = StyleSheet.create({
  wrap: { overflow: 'hidden', backgroundColor: '#F3F0EA' },
});

import { useRef, useMemo, useCallback, useState, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import './CinematicIntro.css';

/* ────────────────────────────────────────────────────────────
   TIMELINE (seconds):
   0–3     Stable rotating wireframe sphere + scanning ring
   3–5     Destabilisation (vertices jitter)
   5–6.5   Break into particles → expand outward
   6.5–8   Collapse to singularity
   8–10    "CRYPTO VAULT" text reveal
   10–11   Fade out overlay → reveal UI
   ──────────────────────────────────────────────────────────── */

const ACCENT = '#00ffa3';

/* ──────── Background star particles ──────── */
function BackgroundStars() {
  const ref = useRef<THREE.Points>(null!);
  const geo = useMemo(() => {
    const count = 600;
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 40;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 40;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 40;
    }
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    return g;
  }, []);

  useFrame(({ clock }) => {
    if (ref.current) {
      ref.current.rotation.y = clock.getElapsedTime() * 0.02;
    }
  });

  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial size={0.04} color={ACCENT} transparent opacity={0.4} sizeAttenuation />
    </points>
  );
}

/* ──────── Inner core glow ──────── */
function InnerCore({ elapsed }: { elapsed: number }) {
  const ref = useRef<THREE.Mesh>(null!);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.getElapsedTime();
    const pulse = 0.15 + Math.sin(t * 3) * 0.05;
    const fade = elapsed >= 6.5 ? Math.max(0, 1 - (elapsed - 6.5) / 1.5) : 1;
    ref.current.scale.setScalar(pulse * fade);
    (ref.current.material as THREE.MeshBasicMaterial).opacity = 0.8 * fade;
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[1, 16, 16]} />
      <meshBasicMaterial color={ACCENT} transparent opacity={0.8} />
    </mesh>
  );
}



/* ──────── Main wireframe sphere → particle system ──────── */
function WireframeSphere({ elapsed }: { elapsed: number }) {
  const pointsRef = useRef<THREE.Points>(null!);
  const linesRef = useRef<THREE.LineSegments>(null!);

  // Build sphere vertex & edge data once
  const { basePos, velocities, jitterSeeds, edgeIdx, vertexCount } = useMemo(() => {
    const geo = new THREE.IcosahedronGeometry(1.5, 4);
    const arr = geo.attributes.position.array as Float32Array;
    const vCount = geo.attributes.position.count;
    const base = new Float32Array(arr);

    // Velocities (explosion direction)
    const vel = new Float32Array(vCount * 3);
    for (let i = 0; i < vCount; i++) {
      const x = base[i * 3], y = base[i * 3 + 1], z = base[i * 3 + 2];
      const len = Math.sqrt(x * x + y * y + z * z) || 1;
      const speed = 0.8 + Math.random() * 1.5;
      vel[i * 3] = (x / len) * speed;
      vel[i * 3 + 1] = (y / len) * speed;
      vel[i * 3 + 2] = (z / len) * speed;
    }

    // Jitter seeds
    const seeds = new Float32Array(vCount * 3);
    for (let i = 0; i < vCount * 3; i++) seeds[i] = Math.random() * 6.28;

    // Unique edges
    const edgeSet = new Set<string>();
    const edges: number[] = [];
    const idx = geo.index;
    if (idx) {
      for (let f = 0; f < idx.count; f += 3) {
        const a = idx.array[f], b = idx.array[f + 1], c = idx.array[f + 2];
        for (const [p, q] of [[a, b], [b, c], [c, a]]) {
          const key = Math.min(p, q) + '-' + Math.max(p, q);
          if (!edgeSet.has(key)) { edgeSet.add(key); edges.push(p, q); }
        }
      }
    }
    geo.dispose();
    return { basePos: base, velocities: vel, jitterSeeds: seeds, edgeIdx: edges, vertexCount: vCount };
  }, []);

  // Create mutable geometries
  const pointsGeo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(basePos), 3));
    return g;
  }, [basePos]);

  const linesGeo = useMemo(() => {
    const linePos = new Float32Array(edgeIdx.length * 3);
    for (let i = 0; i < edgeIdx.length; i++) {
      const vi = edgeIdx[i];
      linePos[i * 3] = basePos[vi * 3];
      linePos[i * 3 + 1] = basePos[vi * 3 + 1];
      linePos[i * 3 + 2] = basePos[vi * 3 + 2];
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(linePos, 3));
    return g;
  }, [basePos, edgeIdx]);

  useFrame(() => {
    if (!pointsRef.current) return;
    const t = elapsed;
    const pAttr = pointsGeo.attributes.position as THREE.BufferAttribute;
    const pArr = pAttr.array as Float32Array;

    for (let i = 0; i < vertexCount; i++) {
      let x = basePos[i * 3], y = basePos[i * 3 + 1], z = basePos[i * 3 + 2];

      if (t >= 3 && t < 5) {
        // Destabilise
        const intensity = ((t - 3) / 2) * 0.15;
        x += Math.sin(t * 8 + jitterSeeds[i * 3]) * intensity;
        y += Math.sin(t * 9 + jitterSeeds[i * 3 + 1]) * intensity;
        z += Math.sin(t * 7 + jitterSeeds[i * 3 + 2]) * intensity;
      } else if (t >= 5 && t < 6.5) {
        // Explode
        const ease = ((t - 5) / 1.5) ** 2;
        x += velocities[i * 3] * ease * 2.5;
        y += velocities[i * 3 + 1] * ease * 2.5;
        z += velocities[i * 3 + 2] * ease * 2.5;
      } else if (t >= 6.5 && t < 8) {
        // Collapse
        const ease = 1 - (1 - (t - 6.5) / 1.5) ** 2;
        const ex = basePos[i * 3] + velocities[i * 3] * 2.5;
        const ey = basePos[i * 3 + 1] + velocities[i * 3 + 1] * 2.5;
        const ez = basePos[i * 3 + 2] + velocities[i * 3 + 2] * 2.5;
        x = ex * (1 - ease);
        y = ey * (1 - ease);
        z = ez * (1 - ease);
      } else if (t >= 8) {
        x = 0; y = 0; z = 0;
      }

      pArr[i * 3] = x;
      pArr[i * 3 + 1] = y;
      pArr[i * 3 + 2] = z;
    }
    pAttr.needsUpdate = true;

    // Update edges
    if (linesRef.current && t < 8) {
      const lAttr = linesGeo.attributes.position as THREE.BufferAttribute;
      const lArr = lAttr.array as Float32Array;
      for (let i = 0; i < edgeIdx.length; i++) {
        const vi = edgeIdx[i];
        lArr[i * 3] = pArr[vi * 3];
        lArr[i * 3 + 1] = pArr[vi * 3 + 1];
        lArr[i * 3 + 2] = pArr[vi * 3 + 2];
      }
      lAttr.needsUpdate = true;
      (linesRef.current.material as THREE.LineBasicMaterial).opacity =
        t >= 5 ? Math.max(0, 1 - (t - 5) * 0.7) : 0.3;
    }

    // Rotate during stable + destabilise phases
    if (t < 5) {
      pointsRef.current.rotation.y = t * 0.3;
      if (linesRef.current) linesRef.current.rotation.y = t * 0.3;
    }
  });

  return (
    <group>
      <lineSegments ref={linesRef} geometry={linesGeo}>
        <lineBasicMaterial color={ACCENT} transparent opacity={0.3} />
      </lineSegments>
      <points ref={pointsRef} geometry={pointsGeo}>
        <pointsMaterial size={0.03} color={ACCENT} transparent opacity={0.9} sizeAttenuation />
      </points>
    </group>
  );
}

/* ──────── Scene orchestrator ──────── */
function Scene({ onComplete }: { onComplete: () => void }) {
  const startTime = useRef(performance.now());
  const [elapsed, setElapsed] = useState(0);
  const done = useRef(false);

  // Set background color
  const { scene } = useThree();
  useMemo(() => {
    scene.background = new THREE.Color('#050a0e');
    scene.fog = new THREE.Fog('#050a0e', 8, 25);
  }, [scene]);

  useFrame(() => {
    const t = (performance.now() - startTime.current) / 1000;
    setElapsed(t);
    if (t >= 10 && !done.current) {
      done.current = true;
      onComplete();
    }
  });

  return (
    <>
      <BackgroundStars />
      <InnerCore elapsed={elapsed} />
      <WireframeSphere elapsed={elapsed} />

      <EffectComposer>
        <Bloom intensity={1.5} luminanceThreshold={0.1} luminanceSmoothing={0.9} mipmapBlur />
      </EffectComposer>
    </>
  );
}

/* ──────── Main CinematicIntro component ──────── */
export default function CinematicIntro({ onFinished }: { onFinished: () => void }) {
  const [showCanvas, setShowCanvas] = useState(true);
  const [showTitle, setShowTitle] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

  const handleSceneComplete = useCallback(() => {
    setShowTitle(true);
  }, []);

  useEffect(() => {
    if (showTitle) {
      const id = setTimeout(() => setFadeOut(true), 5000);
      return () => clearTimeout(id);
    }
  }, [showTitle]);

  useEffect(() => {
    if (fadeOut) {
      const id = setTimeout(() => { setShowCanvas(false); onFinished(); }, 1000);
      return () => clearTimeout(id);
    }
  }, [fadeOut, onFinished]);

  if (!showCanvas) return null;

  return (
    <div className={`cinematic-intro ${fadeOut ? 'cinematic-fade-out' : ''}`}>
      <Canvas camera={{ position: [0, 0, 5], fov: 60 }} dpr={[1, 2]}>
        <Scene onComplete={handleSceneComplete} />
      </Canvas>

      {showTitle && (
        <div className="cinematic-title-overlay">
          <div className="cinematic-title">
            <span className="cinematic-title-crypto">CRYPTO</span>
            <span className="cinematic-title-vault">VAULT</span>
          </div>
          <div className="cinematic-tagline">BLOCKCHAIN INTELLIGENCE SYSTEM</div>
        </div>
      )}

      <div className="cinematic-scanlines" />
    </div>
  );
}

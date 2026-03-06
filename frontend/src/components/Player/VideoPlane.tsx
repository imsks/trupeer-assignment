import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { usePlayerStore } from "../../store/playerStore";

interface Props {
  videoElement: HTMLVideoElement;
}

function createRoundedRectShape(
  w: number,
  h: number,
  r: number,
): THREE.Shape {
  const shape = new THREE.Shape();
  const x = -w / 2;
  const y = -h / 2;

  shape.moveTo(x + r, y);
  shape.lineTo(x + w - r, y);
  shape.quadraticCurveTo(x + w, y, x + w, y + r);
  shape.lineTo(x + w, y + h - r);
  shape.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  shape.lineTo(x + r, y + h);
  shape.quadraticCurveTo(x, y + h, x, y + h - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);

  return shape;
}

export default function VideoPlane({ videoElement }: Props) {
  const { viewport } = useThree();
  const meshRef = useRef<THREE.Mesh>(null);

  const padding = usePlayerStore((s) => s.padding);
  const rounding = usePlayerStore((s) => s.rounding);

  const videoTexture = useMemo(() => {
    const tex = new THREE.VideoTexture(videoElement);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, [videoElement]);

  useFrame(() => {
    if (videoTexture) videoTexture.needsUpdate = true;
  });

  const paddingFraction = padding / 32;
  const videoWidth = viewport.width * 0.65 * (1 - paddingFraction * 0.5);
  const videoHeight = viewport.height * 0.75 * (1 - paddingFraction * 0.5);
  const cornerRadius = (rounding / 32) * Math.min(videoWidth, videoHeight) * 0.15;

  const geometry = useMemo(() => {
    const shape = createRoundedRectShape(videoWidth, videoHeight, cornerRadius);
    const geo = new THREE.ShapeGeometry(shape, 32);

    const pos = geo.attributes.position;
    const uv = new Float32Array(pos.count * 2);
    for (let i = 0; i < pos.count; i++) {
      uv[i * 2] = (pos.getX(i) + videoWidth / 2) / videoWidth;
      uv[i * 2 + 1] = (pos.getY(i) + videoHeight / 2) / videoHeight;
    }
    geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    return geo;
  }, [videoWidth, videoHeight, cornerRadius]);

  useEffect(() => {
    return () => {
      geometry.dispose();
    };
  }, [geometry]);

  return (
    <mesh ref={meshRef} position={[0, 0, 0]} geometry={geometry}>
      <meshBasicMaterial map={videoTexture} toneMapped={false} />
    </mesh>
  );
}

import { useTexture } from "@react-three/drei";
import { useThree } from "@react-three/fiber";

interface Props {
  src: string;
}

export default function BackgroundPlane({ src }: Props) {
  const texture = useTexture(src);
  const { viewport } = useThree();

  return (
    <mesh position={[0, 0, -1]}>
      <planeGeometry args={[viewport.width, viewport.height]} />
      <meshBasicMaterial map={texture} />
    </mesh>
  );
}

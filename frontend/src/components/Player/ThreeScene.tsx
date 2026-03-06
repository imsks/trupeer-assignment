import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import BackgroundPlane from "./BackgroundPlane";
import VideoPlane from "./VideoPlane";

interface Props {
  videoElement: HTMLVideoElement | null;
  backgroundSrc: string;
}

export default function ThreeScene({ videoElement, backgroundSrc }: Props) {
  return (
    <Canvas
      orthographic
      camera={{ zoom: 1, position: [0, 0, 5], near: 0.1, far: 100 }}
      gl={{ antialias: true, alpha: false }}
      style={{ width: "100%", height: "100%" }}
    >
      <Suspense fallback={null}>
        <BackgroundPlane src={backgroundSrc} />
        {videoElement && <VideoPlane videoElement={videoElement} />}
      </Suspense>
    </Canvas>
  );
}

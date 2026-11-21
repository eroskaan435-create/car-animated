import {useThree} from '@react-three/fiber';
import {ThreeCanvas} from '@remotion/three';
import React, {useLayoutEffect, useMemo, useState} from 'react';
import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';
import * as THREE from 'three';
import type {ImageInfo} from '../types';
import type {Framed} from '../util';

const vert = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

// 2.5D parallax: displace texture lookups by (depth - focus) * offset, iterated
// a few times so near objects (the car) move against the background.
const frag = /* glsl */ `
uniform sampler2D uTex;
uniform sampler2D uDepth;
uniform vec4 uRect;     // image rect in frame: x, y (top-left, 0..1), w, h
uniform vec2 uOffset;   // parallax amount in texture uv
uniform float uFocus;   // depth that stays still
varying vec2 vUv;
void main() {
  float u = (vUv.x - uRect.x) / uRect.z;
  float vi = ((1.0 - vUv.y) - uRect.y) / uRect.w;
  vec2 base = vec2(u, 1.0 - vi);
  float edge = min(min(base.x, 1.0 - base.x), min(base.y, 1.0 - base.y));
  if (edge < 0.0) discard;
  vec2 tv = base;
  for (int i = 0; i < 6; i++) {
    float d = texture2D(uDepth, clamp(tv, 0.0, 1.0)).r;
    tv = base + uOffset * (d - uFocus);
  }
  vec3 col = texture2D(uTex, clamp(tv, 0.001, 0.999)).rgb;
  float a = smoothstep(0.0, 0.025, edge);
  gl_FragColor = vec4(col, a);
}
`;

const loader = new THREE.TextureLoader();

const Plane: React.FC<{img: ImageInfo; framed: Framed; W: number; H: number; offset: [number, number]}> = ({
	img,
	framed,
	W,
	H,
	offset,
}) => {
	const {advance} = useThree();
	const [handle] = useState(() => delayRender(`textures ${img.src}`));
	const [tex, setTex] = useState<{c: THREE.Texture; d: THREE.Texture} | null>(null);

	useLayoutEffect(() => {
		let alive = true;
		Promise.all([
			loader.loadAsync(staticFile(img.src)),
			loader.loadAsync(staticFile(img.depth ?? img.src)),
		])
			.then(([c, d]) => {
				if (!alive) return;
				c.anisotropy = 4;
				d.generateMipmaps = false;
				d.minFilter = THREE.LinearFilter;
				setTex({c, d});
			})
			.catch((e) => cancelRender(e));
		return () => {
			alive = false;
		};
	}, [img.src, img.depth]);

	const uniforms = useMemo(
		() => ({
			uTex: {value: null as THREE.Texture | null},
			uDepth: {value: null as THREE.Texture | null},
			uRect: {value: new THREE.Vector4()},
			uOffset: {value: new THREE.Vector2()},
			uFocus: {value: 0.5},
		}),
		[],
	);
	uniforms.uTex.value = tex?.c ?? null;
	uniforms.uDepth.value = tex?.d ?? null;
	uniforms.uRect.value.set(framed.left / W, framed.top / H, framed.dw / W, framed.dh / H);
	uniforms.uOffset.value.set(offset[0], offset[1]);
	uniforms.uFocus.value = img.carDepth ?? 0.6;

	useLayoutEffect(() => {
		if (!tex) return;
		advance(performance.now());
		continueRender(handle);
	}, [tex, advance, handle]);

	if (!tex) return null;
	return (
		<mesh frustumCulled={false}>
			<planeGeometry args={[2, 2]} />
			<shaderMaterial
				uniforms={uniforms}
				vertexShader={vert}
				fragmentShader={frag}
				transparent
				depthTest={false}
				depthWrite={false}
				toneMapped={false}
			/>
		</mesh>
	);
};

export const DepthImage: React.FC<{
	img: ImageInfo;
	framed: Framed;
	W: number;
	H: number;
	offset: [number, number];
	style?: React.CSSProperties;
}> = ({img, framed, W, H, offset, style}) => {
	return (
		<ThreeCanvas
			width={W}
			height={H}
			style={{position: 'absolute', inset: 0, ...style}}
			gl={{alpha: true, antialias: false, preserveDrawingBuffer: true}}
			flat
			linear
		>
			<Plane img={img} framed={framed} W={W} H={H} offset={offset} />
		</ThreeCanvas>
	);
};

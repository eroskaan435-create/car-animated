import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {font} from '../fonts';
import {Distort, SpeedLines} from '../fx/fx';
import {Photo} from '../fx/layers';
import {Caption} from '../fx/text';
import type {Scene} from '../types';
import {clamp, easeInOut, easeOut, type Framed, frameImage, lerp, unit, useManifest} from '../util';

/** One montage shot: a camera move over a single photo. */
export const Shot: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const S = unit(W, H);
	const {theme} = m;
	const B = m.beatFrames;
	const D = scene.duration;
	const img = m.images[scene.image ?? 0];
	const p = clamp(f / D, 0, 1);
	const [x0, y0, x1, y1] = img.box;
	const bw = x1 - x0;
	const cy = (y0 + y1) / 2;
	const move = scene.move ?? 'pushIn';

	let framed: Framed;
	let depthOffset: [number, number] | null = null;
	let blurX = 0;
	let speed = 0;
	let speedDir: 1 | -1 = -1;

	switch (move) {
		case 'pullOut':
			framed = frameImage(img, W, H, 'cover', 1.38 - 0.32 * easeOut(p));
			break;
		case 'panLR':
		case 'panRL': {
			const a = x0 + bw * 0.12;
			const b = x1 - bw * 0.12;
			const t = easeInOut(p);
			const fx = move === 'panLR' ? lerp(a, b, t) : lerp(b, a, t);
			framed = frameImage(img, W, H, 'cover', 1.08, [fx, cy]);
			speed = 0.6 * Math.sin(p * Math.PI);
			speedDir = move === 'panLR' ? -1 : 1;
			break;
		}
		case 'punch': {
			// Snap-zoom on each beat into a different detail of the car.
			const k = Math.floor(f / B);
			const sp = spring({frame: f - k * B, fps, config: {damping: 14, stiffness: 220, mass: 0.5}});
			const zPrev = 1.02 + 0.2 * Math.max(0, k - 1);
			const zNow = 1.02 + 0.2 * k;
			const pts: [number, number][] = [
				[(x0 + x1) / 2, cy],
				[x1 - bw * 0.22, cy + (y1 - y0) * 0.1],
				[x0 + bw * 0.22, cy + (y1 - y0) * 0.1],
				[(x0 + x1) / 2, y0 + (y1 - y0) * 0.35],
			];
			const a = pts[Math.max(0, k - 1) % pts.length];
			const b = pts[k % pts.length];
			const z = k === 0 ? 1.02 + 0.04 * p : lerp(zPrev, zNow, sp);
			const fp: [number, number] = k === 0 ? b : [lerp(a[0], b[0], sp), lerp(a[1], b[1], sp)];
			framed = frameImage(img, W, H, 'cover', z, fp);
			blurX = k > 0 ? (1 - sp) * 10 * S : 0;
			break;
		}
		case 'depth':
			framed = frameImage(img, W, H, 'cover', 1.05 + 0.12 * easeInOut(p));
			depthOffset = [lerp(-0.03, 0.03, easeInOut(p)), lerp(0.006, -0.006, p)];
			break;
		case 'slide': {
			framed = frameImage(img, W, H, 'car', 1.03 + 0.04 * p);
			const k = 1 - easeOut(clamp(f / (B * 0.9), 0, 1));
			framed = {...framed, left: framed.left + k * W * 0.9 - p * W * 0.04};
			blurX = k * 60 * S;
			speed = 0.4 + k;
			break;
		}
		case 'pushIn':
		default:
			framed = frameImage(img, W, H, 'car', 1 + 0.2 * easeInOut(p));
	}

	const sweep = theme.fx.lightSweep && img.cutout && (move === 'pushIn' || move === 'slide' || move === 'pullOut') ? (f - D * 0.3) / (D * 0.55) : 0;
	const vertical = H > W;

	return (
		<AbsoluteFill>
			<Distort blurX={blurX}>
				<Photo img={img} framed={framed} depthOffset={depthOffset} sweep={sweep} sweepColor={theme.accent2} />
			</Distort>
			{theme.fx.speedLines && speed > 0 && !scene.calm ? <SpeedLines intensity={speed} seed={`s${scene.from}`} dir={speedDir} /> : null}
			<Caption
				text={img.caption}
				start={Math.round(B * 0.5)}
				end={D}
				accent={theme.accent}
				font={font(theme.fontBody)}
				size={(vertical ? 40 : 34) * S}
				style={scene.calm ? {left: W * 0.04, top: H * 0.13} : {left: W * 0.06, bottom: H * (vertical ? 0.17 : 0.1)}}
			/>
		</AbsoluteFill>
	);
};

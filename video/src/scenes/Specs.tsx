import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {font} from '../fonts';
import {Distort, Particles} from '../fx/fx';
import {Counter} from '../fx/text';
import type {Scene, Theme} from '../types';
import {clamp, easeOut, hexA, unit, useManifest} from '../util';

const Floor: React.FC<{theme: Theme}> = ({theme}) => {
	const f = useCurrentFrame();
	const {width: W, height: H} = useVideoConfig();
	const S = unit(W, H);
	if (theme.fx.floor === 'grid') {
		const cell = 90 * S;
		return (
			<div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: H * 0.42, perspective: 700 * S, overflow: 'hidden'}}>
				<div
					style={{
						position: 'absolute',
						left: '-60%',
						right: '-60%',
						top: 0,
						bottom: '-40%',
						transformOrigin: '50% 0%',
						transform: 'rotateX(68deg)',
						backgroundImage: `repeating-linear-gradient(0deg, ${hexA(theme.accent, 0.55)} 0 ${2 * S}px, transparent ${2 * S}px ${cell}px), repeating-linear-gradient(90deg, ${hexA(theme.accent, 0.4)} 0 ${2 * S}px, transparent ${2 * S}px ${cell}px)`,
						backgroundPosition: `0 ${(f * 9 * S) % cell}px`,
						WebkitMaskImage: 'linear-gradient(to bottom, transparent, #000 35%)',
						maskImage: 'linear-gradient(to bottom, transparent, #000 35%)',
					}}
				/>
			</div>
		);
	}
	return (
		<>
			<AbsoluteFill
				style={{
					background: `conic-gradient(from 160deg at 50% -10%, transparent 0deg, ${hexA(theme.accent2, 0.13)} 15deg, transparent 30deg, transparent 330deg)`,
				}}
			/>
			<AbsoluteFill style={{background: `radial-gradient(ellipse 55% 14% at 50% 80%, ${hexA(theme.accent2, 0.35)}, transparent 70%)`}} />
		</>
	);
};

export const Specs: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const S = unit(W, H);
	const {theme, car} = m;
	const img = m.images[scene.image ?? 0];
	const D = scene.duration;
	const vertical = H > W * 1.1;
	const cues: number[] = scene.cues?.cards ?? [];
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);

	// ---- car placement
	const [x0, y0, x1, y1] = img.box;
	const targetW = vertical ? W * 0.94 : W * 0.56;
	const cx = vertical ? W / 2 : W * 0.63;
	const bottomY = vertical ? H * 0.82 : H * 0.86;
	const enter = 1 - easeOut(clamp(f / 12, 0, 1));
	const drift = 1 + 0.05 * (f / D);
	const s = (targetW / ((x1 - x0) * img.w)) * drift;
	const dw = img.w * s;
	const dh = img.h * s;
	const left = cx - ((x0 + x1) / 2) * dw - enter * W * 1.1;
	const top = bottomY - y1 * dh;

	const cards = car.specs.slice(0, 4);
	const header = clamp(f / 10, 0, 1);

	return (
		<AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 72%, ${hexA(theme.accent, 0.35)} 0%, ${theme.bg} 58%, #000 100%)`}}>
			<Floor theme={theme} />
			<Particles kind={theme.fx.particles} accent={theme.accent} seed="specs" intensity={0.6} />

			<Distort blurX={enter * 80 * S}>
				{img.cutout ? (
					<>
						<div
							style={{
								position: 'absolute',
								left: left + x0 * dw,
								width: (x1 - x0) * dw,
								top: bottomY - 22 * S,
								height: 44 * S,
								borderRadius: '50%',
								background: 'radial-gradient(ellipse, rgba(0,0,0,0.85), transparent 70%)',
							}}
						/>
						<Img
							src={staticFile(img.cutout)}
							style={{
								position: 'absolute',
								left,
								width: dw,
								height: dh,
								top: 2 * bottomY - top - dh,
								transform: 'scaleY(-1)',
								opacity: 0.22,
								WebkitMaskImage: `linear-gradient(to bottom, transparent ${y0 * 100 + (y1 - y0) * 45}%, #000 ${y1 * 100}%)`,
								maskImage: `linear-gradient(to bottom, transparent ${y0 * 100 + (y1 - y0) * 45}%, #000 ${y1 * 100}%)`,
							}}
						/>
						<Img src={staticFile(img.cutout)} style={{position: 'absolute', left, top, width: dw, height: dh}} />
					</>
				) : (
					<div
						style={{
							position: 'absolute',
							left: cx - targetW / 2 - enter * W * 1.1,
							top: bottomY - targetW * 0.62,
							width: targetW,
							height: targetW * 0.62,
							borderRadius: 26 * S,
							overflow: 'hidden',
							border: `${3 * S}px solid ${theme.accent}`,
							boxShadow: `0 0 ${50 * S}px ${hexA(theme.accent, 0.5)}`,
						}}
					>
						<Img
							src={staticFile(img.src)}
							style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: `${((x0 + x1) / 2) * 100}% ${((y0 + y1) / 2) * 100}%`}}
						/>
					</div>
				)}
			</Distort>

			{/* header */}
			<div
				style={{
					position: 'absolute',
					top: H * (vertical ? 0.045 : 0.06),
					left: vertical ? 0 : W * 0.05,
					right: vertical ? 0 : undefined,
					textAlign: vertical ? 'center' : 'left',
					opacity: header,
					transform: `translateY(${(1 - header) * -30 * S}px)`,
				}}
			>
				<div style={{fontFamily: body, fontWeight: 700, fontSize: 28 * S, letterSpacing: '0.4em', color: theme.accent}}>PERFORMANCE</div>
				<div style={{fontFamily: display, fontWeight: 800, fontSize: 64 * S, color: '#fff', lineHeight: 1.05, textTransform: 'uppercase'}}>
					{car.title}
				</div>
			</div>

			{/* spec cards */}
			{cards.map((c, i) => {
				const cue = cues[i] ?? 0;
				const sp = spring({frame: f - cue, fps, config: {damping: 13, stiffness: 170, mass: 0.6}});
				if (f < cue) return null;
				const glow = Math.exp(-(f - cue) / 6);
				const col = i % 2;
				const row = Math.floor(i / 2);
				const pos = vertical
					? {left: W * (col ? 0.52 : 0.06), top: H * (0.17 + row * 0.155), width: W * 0.42, height: H * 0.135}
					: {left: W * 0.05, top: H * (0.27 + i * 0.165), width: W * 0.3, height: H * 0.14};
				return (
					<div
						key={i}
						style={{
							position: 'absolute',
							...pos,
							transform: `translateY(${interpolate(sp, [0, 1], [50 * S, 0])}px) scale(${interpolate(sp, [0, 1], [0.7, 1])})`,
							opacity: clamp(sp * 2, 0, 1),
							background: `linear-gradient(135deg, ${hexA('#ffffff', 0.1)}, ${hexA('#ffffff', 0.02)})`,
							border: `${1.5 * S}px solid ${hexA(theme.accent, 0.5 + glow * 0.5)}`,
							borderLeft: `${7 * S}px solid ${theme.accent}`,
							borderRadius: 14 * S,
							boxShadow: `0 0 ${(20 + glow * 50) * S}px ${hexA(theme.accent, 0.25 + glow * 0.5)}`,
							padding: `${14 * S}px ${24 * S}px`,
							display: 'flex',
							flexDirection: 'column',
							justifyContent: 'center',
							overflow: 'hidden',
						}}
					>
						<div style={{fontFamily: body, fontWeight: 700, fontSize: 26 * S, letterSpacing: '0.18em', color: hexA('#ffffff', 0.75), textTransform: 'uppercase', whiteSpace: 'nowrap'}}>
							{c.label}
						</div>
						<div style={{fontFamily: display, fontWeight: 800, fontSize: (vertical ? 70 : 62) * S, color: '#fff', lineHeight: 1.05, whiteSpace: 'nowrap'}}>
							<Counter value={c.value} start={cue} duration={16} />
						</div>
					</div>
				);
			})}
		</AbsoluteFill>
	);
};

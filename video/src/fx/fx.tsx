import React, {useId} from 'react';
import {AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp, hexA, unit} from '../util';

const sid = (s: string) => s.replace(/[^a-zA-Z0-9]/g, '');

/** Wrap children in a directional (horizontal) motion blur + optional RGB split. */
export const Distort: React.FC<{
	blurX?: number;
	blurY?: number;
	rgb?: number;
	children: React.ReactNode;
	style?: React.CSSProperties;
}> = ({blurX = 0, blurY = 0, rgb = 0, children, style}) => {
	const id = sid(useId());
	const useBlur = blurX > 0.5 || blurY > 0.5;
	const useRgb = Math.abs(rgb) > 0.5;
	if (!useBlur && !useRgb) return <AbsoluteFill style={style}>{children}</AbsoluteFill>;
	return (
		<AbsoluteFill style={{...style, filter: `url(#${id})`}}>
			<svg width="0" height="0" style={{position: 'absolute'}}>
				<filter id={id} x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
					{useBlur ? <feGaussianBlur in="SourceGraphic" stdDeviation={`${blurX} ${blurY}`} result="b" /> : null}
					{useRgb ? (
						<>
							<feOffset in={useBlur ? 'b' : 'SourceGraphic'} dx={-rgb} result="r0" />
							<feColorMatrix in="r0" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
							<feColorMatrix in={useBlur ? 'b' : 'SourceGraphic'} type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
							<feOffset in={useBlur ? 'b' : 'SourceGraphic'} dx={rgb} dy={rgb * 0.3} result="b0" />
							<feColorMatrix in="b0" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="bb" />
							<feBlend in="r" in2="g" mode="screen" result="rg" />
							<feBlend in="rg" in2="bb" mode="screen" />
						</>
					) : null}
				</filter>
			</svg>
			{children}
		</AbsoluteFill>
	);
};

/** Diagonal specular band sweeping across, optionally masked to the car cutout. */
export const LightSweep: React.FC<{progress: number; mask?: string | null; color?: string; strength?: number}> = ({
	progress,
	mask,
	color = '#ffffff',
	strength = 0.85,
}) => {
	if (progress <= 0 || progress >= 1) return null;
	const pos = interpolate(progress, [0, 1], [-60, 160]);
	const maskStyle: React.CSSProperties = mask
		? {
				WebkitMaskImage: `url(${staticFile(mask)})`,
				maskImage: `url(${staticFile(mask)})`,
				WebkitMaskSize: '100% 100%',
				maskSize: '100% 100%',
			}
		: {};
	return (
		<AbsoluteFill
			style={{
				...maskStyle,
				mixBlendMode: 'screen',
				opacity: strength * Math.sin(progress * Math.PI),
				background: `linear-gradient(105deg, transparent ${pos - 18}%, ${hexA(color, 0.15)} ${pos - 8}%, ${hexA(
					color,
					0.95,
				)} ${pos}%, ${hexA(color, 0.15)} ${pos + 6}%, transparent ${pos + 14}%)`,
			}}
		/>
	);
};

/** Horizontal speed streaks. */
export const SpeedLines: React.FC<{intensity?: number; color?: string; seed?: string; dir?: 1 | -1}> = ({
	intensity = 1,
	color = '#ffffff',
	seed = 'sl',
	dir = -1,
}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	if (intensity <= 0.01) return null;
	const lines = Array.from({length: 34}, (_, i) => {
		const r = (k: string) => random(`${seed}-${i}-${k}`);
		const speed = (0.06 + r('s') * 0.09) * width;
		const len = (0.15 + r('l') * 0.5) * width;
		const y = r('y') * height;
		const x0 = r('x') * (width + len);
		let x = (x0 + dir * frame * speed) % (width + len);
		if (x < 0) x += width + len;
		return {x: x - len, y, len, th: 1 + r('t') * 3, op: 0.15 + r('o') * 0.5};
	});
	return (
		<AbsoluteFill style={{opacity: clamp(intensity, 0, 1), pointerEvents: 'none'}}>
			{lines.map((l, i) => (
				<div
					key={i}
					style={{
						position: 'absolute',
						left: l.x,
						top: l.y,
						width: l.len,
						height: l.th,
						opacity: l.op,
						background: `linear-gradient(${dir < 0 ? 90 : 270}deg, transparent, ${color})`,
						borderRadius: l.th,
					}}
				/>
			))}
		</AbsoluteFill>
	);
};

/** Particle field: sparks, dust, bokeh or neon. */
export const Particles: React.FC<{kind: string; accent: string; seed?: string; intensity?: number; burstAt?: number}> = ({
	kind,
	accent,
	seed = 'p',
	intensity = 1,
	burstAt,
}) => {
	const frame = useCurrentFrame();
	const {width, height, fps} = useVideoConfig();
	const S = unit(width, height);
	if (kind === 'none' || intensity <= 0) return null;
	const n = kind === 'sparks' ? 46 : kind === 'bokeh' ? 22 : kind === 'dust' ? 30 : 40;
	const items = Array.from({length: n}, (_, i) => {
		const r = (k: string) => random(`${seed}-${kind}-${i}-${k}`);
		const life = (kind === 'sparks' ? 0.8 + r('l') * 0.9 : 3 + r('l') * 4) * fps;
		const t0 = r('t') * life;
		const t = burstAt !== undefined ? frame - burstAt : (frame + t0) % life;
		if (t < 0) return null;
		const p = t / life;
		if (burstAt !== undefined && p > 1) return null;
		let x: number, y: number, size: number, op: number, color: string, blur = 0, w = 0, rot = 0;
		if (kind === 'sparks') {
			const ang = burstAt !== undefined ? r('a') * Math.PI * 2 : -Math.PI / 2 + (r('a') - 0.5) * 1.6;
			const v = (burstAt !== undefined ? 0.5 + r('v') : 0.3 + r('v') * 0.5) * height;
			const ox = burstAt !== undefined ? width / 2 : r('x') * width;
			const oy = burstAt !== undefined ? height / 2 : height * (0.75 + r('y') * 0.3);
			x = ox + Math.cos(ang) * v * p;
			y = oy + Math.sin(ang) * v * p + 0.35 * height * p * p;
			size = (3 + r('s') * 4) * S;
			w = size * (4 + r('w') * 6);
			op = (1 - p) * (0.6 + r('o') * 0.4);
			color = r('c') > 0.5 ? accent : '#ffd27a';
			rot = Math.atan2(Math.sin(ang) * v + 0.7 * height * p, Math.cos(ang) * v);
		} else if (kind === 'bokeh') {
			x = r('x') * width + Math.sin(p * 6 + i) * 30 * S;
			y = height * (1.05 - p * 1.1);
			size = (30 + r('s') * 90) * S;
			op = Math.sin(p * Math.PI) * (0.12 + r('o') * 0.2);
			color = r('c') > 0.4 ? accent : '#ffffff';
			blur = size * 0.15;
		} else if (kind === 'dust') {
			x = (r('x') * width + p * 0.3 * width) % width;
			y = r('y') * height + Math.sin(p * 4 + i) * 40 * S;
			size = (6 + r('s') * 22) * S;
			op = Math.sin(p * Math.PI) * (0.15 + r('o') * 0.25);
			color = '#e8c9a0';
			blur = size * 0.4;
		} else {
			x = r('x') * width;
			y = height * (1.05 - p * 1.1);
			size = (3 + r('s') * 6) * S;
			op = Math.sin(p * Math.PI) * (0.5 + r('o') * 0.5);
			color = r('c') > 0.5 ? accent : '#ffffff';
		}
		return {x, y, size, op, color, blur, w, rot};
	});
	return (
		<AbsoluteFill style={{opacity: clamp(intensity, 0, 1), pointerEvents: 'none', mixBlendMode: 'screen'}}>
			{items.map((it, i) =>
				it ? (
					<div
						key={i}
						style={{
							position: 'absolute',
							left: it.x,
							top: it.y,
							width: kind === 'sparks' ? it.w : it.size,
							height: it.size,
							borderRadius: kind === 'neon' ? 2 : 999,
							background: kind === 'sparks' ? `linear-gradient(90deg, transparent, ${it.color})` : it.color,
							opacity: it.op,
							filter: it.blur ? `blur(${it.blur}px)` : undefined,
							boxShadow: kind === 'neon' || kind === 'sparks' ? `0 0 ${it.size * 3}px ${it.color}` : undefined,
							transform: `translate(-50%,-50%) rotate(${it.rot}rad)`,
						}}
					/>
				) : null,
			)}
		</AbsoluteFill>
	);
};

/** Headlight-like light streaks used in the intro. */
export const Streaks: React.FC<{accent: string; accent2: string; speed?: number}> = ({accent, accent2, speed = 1}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const lines = Array.from({length: 18}, (_, i) => {
		const r = (k: string) => random(`streak-${i}-${k}`);
		const len = (0.3 + r('l') * 0.7) * width;
		const v = (0.03 + r('v') * 0.05) * width * speed;
		const total = width + len;
		const x = ((r('x') * total + frame * v * (1 + frame / 60)) % total) - len;
		return {x, y: height * (0.15 + r('y') * 0.7), len, th: (2 + r('t') * 6) * unit(width, height), c: r('c') > 0.5 ? accent : accent2, op: 0.3 + r('o') * 0.7};
	});
	return (
		<AbsoluteFill style={{mixBlendMode: 'screen'}}>
			{lines.map((l, i) => (
				<div
					key={i}
					style={{
						position: 'absolute',
						left: l.x,
						top: l.y,
						width: l.len,
						height: l.th,
						opacity: l.op,
						borderRadius: l.th,
						background: `linear-gradient(90deg, transparent, ${l.c} 70%, #fff)`,
						boxShadow: `0 0 ${l.th * 6}px ${l.c}`,
					}}
				/>
			))}
		</AbsoluteFill>
	);
};

/** Film grain from a pre-generated tile, jittered every frame. */
export const Grain: React.FC<{src: string | null; amount: number}> = ({src, amount}) => {
	const frame = useCurrentFrame();
	if (!src || amount <= 0) return null;
	const x = Math.floor(random(`gx${frame}`) * 256);
	const y = Math.floor(random(`gy${frame}`) * 256);
	return (
		<AbsoluteFill
			style={{
				backgroundImage: `url(${staticFile(src)})`,
				backgroundRepeat: 'repeat',
				backgroundPosition: `${x}px ${y}px`,
				backgroundSize: '256px 256px',
				opacity: clamp(amount * 4, 0, 1),
				pointerEvents: 'none',
			}}
		/>
	);
};

export const Vignette: React.FC<{strength?: number}> = ({strength = 0.55}) => (
	<AbsoluteFill
		style={{background: `radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,${strength}) 100%)`, pointerEvents: 'none'}}
	/>
);

/** Expanding shockwave ring. */
export const Shockwave: React.FC<{at: number; color: string; x?: string; y?: string}> = ({at, color, x = '50%', y = '50%'}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const t = frame - at;
	if (t < 0 || t > 18) return null;
	const p = t / 18;
	const size = Math.max(width, height) * 1.4 * (1 - Math.pow(1 - p, 3));
	return (
		<div
			style={{
				position: 'absolute',
				left: x,
				top: y,
				width: size,
				height: size,
				transform: 'translate(-50%,-50%)',
				borderRadius: '50%',
				border: `${(1 - p) * 26 * unit(width, height)}px solid ${color}`,
				opacity: 1 - p,
				boxShadow: `0 0 60px ${color}`,
			}}
		/>
	);
};

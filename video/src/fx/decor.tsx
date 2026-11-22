/**
 * Long-video decoration: a "sizzling" car-themed frame around the picture and cute
 * Japanese-style (kawaii) car stickers that pop in one by one (every `stickerEvery` seconds)
 * and stay on screen. All artwork is drawn here as SVG, so there's nothing to license.
 */
import React from 'react';
import {AbsoluteFill, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {font} from '../fonts';
import type {Manifest} from '../types';
import {clamp} from '../util';

export type Decor = {frame?: boolean; stickers?: boolean; stickerEvery?: number; maxStickers?: number};

/** Inset of the picture inside the frame (fractions of width / height). */
export const FRAME_SCALE = 0.93;

// --------------------------------------------------------------------------- frame
type Rect = {x: number; y: number; w: number; h: number};

/** Point at fraction t (0..1) along a rectangle's perimeter, clockwise from the top-left, plus the outward normal. */
function onRect(r: Rect, t: number): {x: number; y: number; nx: number; ny: number} {
	const P = 2 * (r.w + r.h);
	let d = (((t % 1) + 1) % 1) * P;
	if (d < r.w) return {x: r.x + d, y: r.y, nx: 0, ny: -1};
	d -= r.w;
	if (d < r.h) return {x: r.x + r.w, y: r.y + d, nx: 1, ny: 0};
	d -= r.h;
	if (d < r.w) return {x: r.x + r.w - d, y: r.y + r.h, nx: 0, ny: 1};
	d -= r.w;
	return {x: r.x, y: r.y + r.h - d, nx: -1, ny: 0};
}

export const SizzleFrame: React.FC<{accent: string; accent2: string}> = ({accent, accent2}) => {
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const ix = (W * (1 - FRAME_SCALE)) / 2;
	const iy = (H * (1 - FRAME_SCALE)) / 2;
	const inner: Rect = {x: ix, y: iy, w: W - 2 * ix, h: H - 2 * iy};
	const mid: Rect = {x: ix / 2, y: iy / 2, w: W - ix, h: H - iy};
	const P = 2 * (inner.w + inner.h);
	const flicker = 0.78 + 0.22 * Math.abs(Math.sin(f * 0.9) * Math.sin(f * 0.37 + 1));
	const comets = [0, 0.5].map((o) => (o + (f / fps) * 0.07) % 1);
	const cometLen = P * 0.06;

	// sparks thrown off the comet heads
	const sparks: React.ReactNode[] = [];
	comets.forEach((c, ci) => {
		for (let k = 0; k < 26; k++) {
			const life = 22;
			const age = (f + k * 3 + ci * 7) % life;
			const born = f - age;
			const seed = `sp-${ci}-${k}-${Math.floor((f + k * 3 + ci * 7) / life)}`;
			const p = onRect(inner, comets[ci] - (age / fps) * 0.07);
			const spread = (random(seed) - 0.5) * 1.6;
			const sp = 3 + random(seed + 'v') * 6;
			const tx = -p.ny, ty = p.nx; // tangent
			const vx = (p.nx * (0.6 + random(seed + 'o')) + tx * spread) * sp;
			const vy = (p.ny * (0.6 + random(seed + 'o')) + ty * spread) * sp;
			const x = p.x + vx * age;
			const y = p.y + vy * age + 0.12 * age * age;
			const a = 1 - age / life;
			if (born < 0) continue;
			sparks.push(
				<line key={`${ci}-${k}`} x1={x} y1={y} x2={x - vx * 2.4} y2={y - vy * 2.4} stroke={k % 3 ? '#ffd36b' : '#ffffff'} strokeWidth={4 * a + 1} strokeLinecap="round" opacity={a} />,
			);
		}
	});

	// electric crackles flickering along the neon edge
	const crackles: React.ReactNode[] = [];
	for (let c = 0; c < 4; c++) {
		const seed = `cr-${c}-${Math.floor(f / 3)}`;
		if (random(seed + 'on') < 0.35) continue;
		const t0 = random(seed);
		const p0 = onRect(inner, t0);
		const tx = -p0.ny, ty = p0.nx;
		const len = 70 + random(seed + 'l') * 110;
		const pts: string[] = [];
		for (let k = 0; k <= 8; k++) {
			const along = (k / 8) * len;
			const jit = k === 0 || k === 8 ? 0 : (random(`${seed}-${k}`) - 0.5) * 22;
			pts.push(`${p0.x + tx * along + p0.nx * jit},${p0.y + ty * along + p0.ny * jit}`);
		}
		crackles.push(<polyline key={c} points={pts.join(' ')} fill="none" stroke={c % 2 ? '#ffffff' : accent2} strokeWidth={3} strokeLinejoin="round" opacity={0.9} />);
	}

	const cs = iy / 2; // checker square
	const corner = (cx: number, cy: number, key: string) => (
		<g key={key}>
			{[0, 1, 2].flatMap((i) => [0, 1, 2].map((j) => (
				<rect key={`${i}${j}`} x={cx + i * cs} y={cy + j * cs} width={cs} height={cs} fill={(i + j) % 2 ? '#111' : '#f4f4f4'} />
			)))}
		</g>
	);

	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
				<defs>
					<linearGradient id="asphalt" x1="0" y1="0" x2="1" y2="1">
						<stop offset="0" stopColor="#14141c" />
						<stop offset="0.5" stopColor="#23232f" />
						<stop offset="1" stopColor="#101016" />
					</linearGradient>
					<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
						<feGaussianBlur stdDeviation="6" result="b" />
						<feMerge>
							<feMergeNode in="b" />
							<feMergeNode in="SourceGraphic" />
						</feMerge>
					</filter>
				</defs>
				{/* asphalt band */}
				<path
					fillRule="evenodd"
					fill="url(#asphalt)"
					d={`M0 0H${W}V${H}H0Z M${inner.x} ${inner.y}V${inner.y + inner.h}H${inner.x + inner.w}V${inner.y}Z`}
				/>
				{/* road centre line */}
				<rect x={mid.x} y={mid.y} width={mid.w} height={mid.h} fill="none" stroke="#ffd400" strokeWidth={4} strokeDasharray="34 26" opacity={0.85} />
				{corner(0, 0, 'tl')}
				{corner(W - 3 * cs, 0, 'tr')}
				{corner(0, H - 3 * cs, 'bl')}
				{corner(W - 3 * cs, H - 3 * cs, 'br')}
				{/* neon inner edge */}
				<rect x={inner.x} y={inner.y} width={inner.w} height={inner.h} fill="none" stroke={accent} strokeWidth={6} opacity={flicker} filter="url(#glow)" />
				<rect x={inner.x - 5} y={inner.y - 5} width={inner.w + 10} height={inner.h + 10} fill="none" stroke={accent2} strokeWidth={1.5} opacity={0.5 * flicker} />
				{/* headlight comets racing round the frame */}
				{comets.map((c, i) => (
					<g key={i} filter="url(#glow)">
						<rect x={inner.x} y={inner.y} width={inner.w} height={inner.h} fill="none" stroke={accent2} strokeWidth={10}
							strokeDasharray={`${cometLen} ${P - cometLen}`} strokeDashoffset={-(c * P - cometLen)} opacity={0.8} />
						<rect x={inner.x} y={inner.y} width={inner.w} height={inner.h} fill="none" stroke="#ffffff" strokeWidth={4}
							strokeDasharray={`${cometLen * 0.4} ${P - cometLen * 0.4}`} strokeDashoffset={-(c * P - cometLen * 0.4)} />
					</g>
				))}
				<g filter="url(#glow)">{crackles}</g>
				{sparks}
			</svg>
		</AbsoluteFill>
	);
};

// --------------------------------------------------------------------------- kawaii stickers
const INK = '#3b2a35';

const Eye: React.FC<{x: number; y: number; r: number; blink: number}> = ({x, y, r, blink}) => (
	<g>
		<ellipse cx={x} cy={y} rx={r} ry={r * 1.15 * blink} fill={INK} />
		{blink > 0.5 ? (
			<>
				<circle cx={x + r * 0.32} cy={y - r * 0.42} r={r * 0.38} fill="#fff" />
				<circle cx={x - r * 0.3} cy={y + r * 0.35} r={r * 0.16} fill="#fff" />
			</>
		) : null}
	</g>
);

const Face: React.FC<{eyes: [number, number][]; r: number; mouth: [number, number]; cheeks: [number, number][]; blink: number}> = ({eyes, r, mouth, cheeks, blink}) => (
	<g>
		{eyes.map(([x, y], i) => <Eye key={i} x={x} y={y} r={r} blink={blink} />)}
		{cheeks.map(([x, y], i) => <ellipse key={i} cx={x} cy={y} rx={r * 1.1} ry={r * 0.65} fill="#ff7fa3" opacity={0.75} />)}
		<path d={`M${mouth[0] - 7} ${mouth[1]} Q${mouth[0]} ${mouth[1] + 9} ${mouth[0] + 7} ${mouth[1]}`} fill="#ff6b81" stroke={INK} strokeWidth={3} strokeLinejoin="round" />
	</g>
);

const Wheel: React.FC<{x: number; y: number; r: number; spin: number; white?: boolean}> = ({x, y, r, spin, white}) => (
	<g>
		<circle cx={x} cy={y} r={r} fill="#2e2a33" stroke={INK} strokeWidth={4} />
		{white ? <circle cx={x} cy={y} r={r * 0.72} fill="#f4f4f4" /> : null}
		<circle cx={x} cy={y} r={r * 0.48} fill="#d9dde6" stroke={INK} strokeWidth={2.5} />
		<g transform={`rotate(${spin} ${x} ${y})`}>
			{[0, 72, 144, 216, 288].map((a) => (
				<line key={a} x1={x} y1={y} x2={x + Math.cos((a * Math.PI) / 180) * r * 0.42} y2={y + Math.sin((a * Math.PI) / 180) * r * 0.42} stroke="#8a90a0" strokeWidth={3} strokeLinecap="round" />
			))}
		</g>
		<circle cx={x} cy={y} r={r * 0.12} fill={INK} />
	</g>
);

type CarArt = {sil: React.ReactNode; art: (spin: number, blink: number) => React.ReactNode; label: string; color: string};

const GLASS = '#cfefff';

const CARS: CarArt[] = [
	// 1. modern kei box car
	{
		label: 'ブーン!', color: '#5cc9a7',
		sil: <><rect x={26} y={30} width={188} height={102} rx={28} /><circle cx={70} cy={134} r={23} /><circle cx={172} cy={134} r={23} /></>,
		art: (spin, blink) => (
			<>
				<rect x={26} y={30} width={188} height={102} rx={28} fill="#7fdcbf" stroke={INK} strokeWidth={4} />
				<rect x={26} y={30} width={188} height={30} rx={28} fill="#fff8ec" stroke={INK} strokeWidth={4} />
				<rect x={42} y={48} width={58} height={40} rx={10} fill={GLASS} stroke={INK} strokeWidth={4} />
				<path d="M112 48 H178 Q192 48 196 62 L200 88 H112 Z" fill={GLASS} stroke={INK} strokeWidth={4} />
				<line x1={106} y1={48} x2={106} y2={128} stroke={INK} strokeWidth={3} />
				<circle cx={205} cy={104} r={7} fill="#ffe066" stroke={INK} strokeWidth={3} />
				<Face eyes={[[142, 70], [172, 70]]} r={7} mouth={[157, 104]} cheeks={[[128, 106], [186, 106]]} blink={blink} />
				<Wheel x={70} y={134} r={21} spin={spin} />
				<Wheel x={172} y={134} r={21} spin={spin} />
			</>
		),
	},
	// 2. classic round retro car
	{
		label: 'レトロ♪', color: '#f6b93b',
		sil: <><path d="M22 124 Q22 96 50 92 Q64 44 120 42 Q176 44 190 92 Q218 96 218 124 Z" /><circle cx={66} cy={130} r={22} /><circle cx={176} cy={130} r={22} /></>,
		art: (spin, blink) => (
			<>
				<path d="M22 124 Q22 96 50 92 Q64 44 120 42 Q176 44 190 92 Q218 96 218 124 Z" fill="#ffd166" stroke={INK} strokeWidth={4} />
				<path d="M72 90 Q82 58 120 56 Q158 58 168 90 Z" fill={GLASS} stroke={INK} strokeWidth={4} />
				<line x1={120} y1={56} x2={120} y2={90} stroke={INK} strokeWidth={3} />
				<path d="M22 112 H218" stroke="#c9d1dc" strokeWidth={5} />
				<circle cx={204} cy={100} r={9} fill="#fffbe6" stroke={INK} strokeWidth={3} />
				<Face eyes={[[100, 76], [140, 76]]} r={7} mouth={[120, 102]} cheeks={[[86, 104], [154, 104]]} blink={blink} />
				<Wheel x={66} y={130} r={20} spin={spin} white />
				<Wheel x={176} y={130} r={20} spin={spin} white />
			</>
		),
	},
	// 3. modern sports car
	{
		label: 'はやい!', color: '#ff6b6b',
		sil: <><path d="M16 120 Q18 96 48 92 L92 68 Q110 58 142 60 L180 74 Q218 80 226 104 L226 124 Q226 132 214 132 L28 132 Q16 132 16 120 Z" /><path d="M20 96 L14 76 L48 76 L48 92 Z" /><circle cx={62} cy={132} r={21} /><circle cx={182} cy={132} r={21} /></>,
		art: (spin, blink) => (
			<>
				<path d="M20 96 L14 76 L48 76 L48 92 Z" fill="#e63946" stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M16 120 Q18 96 48 92 L92 68 Q110 58 142 60 L180 74 Q218 80 226 104 L226 124 Q226 132 214 132 L28 132 Q16 132 16 120 Z" fill="#ff6b6b" stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M98 74 Q114 64 138 65 L170 80 L100 84 Z" fill={GLASS} stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M30 110 H210" stroke="#fff" strokeWidth={5} strokeDasharray="20 10" />
				<path d="M212 98 L224 100 L222 106 L210 104 Z" fill="#fff3b0" stroke={INK} strokeWidth={2.5} />
				<Face eyes={[[124, 76], [148, 77]]} r={5.5} mouth={[160, 104]} cheeks={[[140, 106], [196, 104]]} blink={blink} />
				<Wheel x={62} y={132} r={19} spin={spin * 1.8} />
				<Wheel x={182} y={132} r={19} spin={spin * 1.8} />
			</>
		),
	},
	// 4. classic 1950s convertible with fins
	{
		label: 'クラシック', color: '#ff8fc7',
		sil: <><path d="M12 112 L18 90 L30 66 L46 92 L60 86 H170 L196 92 Q226 96 228 112 L228 124 Q228 132 218 132 H22 Q12 132 12 122 Z" /><circle cx={60} cy={134} r={19} /><circle cx={184} cy={134} r={19} /></>,
		art: (spin, blink) => (
			<>
				<path d="M150 88 L162 62 L170 62 L162 88 Z" fill={GLASS} stroke={INK} strokeWidth={3.5} />
				<path d="M12 112 L18 90 L30 66 L46 92 L60 86 H170 L196 92 Q226 96 228 112 L228 124 Q228 132 218 132 H22 Q12 132 12 122 Z" fill="#ffadd6" stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M20 112 H222" stroke="#eef2f7" strokeWidth={6} />
				<path d="M64 86 Q80 74 96 86" fill="none" stroke="#c0446f" strokeWidth={4} />
				<circle cx={218} cy={104} r={7} fill="#fffbe6" stroke={INK} strokeWidth={3} />
				<rect x={10} y={96} width={10} height={6} rx={2} fill="#ff4d6d" stroke={INK} strokeWidth={2} />
				<Face eyes={[[108, 100], [134, 100]]} r={6.5} mouth={[121, 120]} cheeks={[[94, 116], [148, 116]]} blink={blink} />
				<Wheel x={60} y={134} r={18} spin={spin} white />
				<Wheel x={184} y={134} r={18} spin={spin} white />
			</>
		),
	},
	// 5. modern EV bubble car
	{
		label: 'エコ!', color: '#6ec1ff',
		sil: <><path d="M26 126 Q22 72 88 52 Q140 38 182 62 Q220 84 216 126 Z" /><circle cx={70} cy={130} r={22} /><circle cx={176} cy={130} r={22} /></>,
		art: (spin, blink) => (
			<>
				<path d="M26 126 Q22 72 88 52 Q140 38 182 62 Q220 84 216 126 Z" fill="#9ad3ff" stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M68 66 Q120 46 170 72 L172 92 H70 Z" fill={GLASS} stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M64 98 L54 116 L64 114 L58 130 L76 106 L66 108 L74 98 Z" fill="#ffe14d" stroke={INK} strokeWidth={2.5} strokeLinejoin="round" />
				<Face eyes={[[108, 80], [144, 80]]} r={7} mouth={[140, 106]} cheeks={[[118, 108], [170, 106]]} blink={blink} />
				<Wheel x={70} y={130} r={20} spin={spin} />
				<Wheel x={176} y={130} r={20} spin={spin} />
			</>
		),
	},
	// 6. classic two-tone camper van
	{
		label: 'ドライブ!', color: '#ff9f68',
		sil: <><rect x={22} y={30} width={198} height={102} rx={26} /><circle cx={70} cy={134} r={22} /><circle cx={178} cy={134} r={22} /></>,
		art: (spin, blink) => (
			<>
				<rect x={22} y={30} width={198} height={102} rx={26} fill="#ff9f68" stroke={INK} strokeWidth={4} />
				<path d="M22 80 V56 Q22 30 48 30 H194 Q220 30 220 56 V80 Z" fill="#fff4dc" stroke={INK} strokeWidth={4} />
				{[38, 80, 122].map((x) => <rect key={x} x={x} y={44} width={32} height={28} rx={7} fill={GLASS} stroke={INK} strokeWidth={3.5} />)}
				<rect x={164} y={44} width={44} height={30} rx={8} fill={GLASS} stroke={INK} strokeWidth={3.5} />
				<path d="M150 92 L170 110 L190 92" fill="none" stroke="#fff4dc" strokeWidth={6} strokeLinecap="round" />
				<Face eyes={[[178, 58], [198, 58]]} r={6} mouth={[188, 120]} cheeks={[[160, 120], [210, 116]]} blink={blink} />
				<Wheel x={70} y={134} r={20} spin={spin} white />
				<Wheel x={178} y={134} r={20} spin={spin} white />
			</>
		),
	},
	// 7. modern kei truck carrying mikan
	{
		label: 'けいトラ!', color: '#f4e3b1',
		sil: <><path d="M150 44 H196 Q214 44 216 62 L220 128 H22 V84 H150 Z" /><circle cx={60} cy={76} r={12} /><circle cx={88} cy={74} r={12} /><circle cx={116} cy={76} r={12} /><circle cx={64} cy={134} r={21} /><circle cx={186} cy={134} r={21} /></>,
		art: (spin, blink) => (
			<>
				{[[60, 76], [88, 74], [116, 76], [74, 66], [102, 64]].map(([x, y], i) => (
					<g key={i}>
						<circle cx={x} cy={y} r={11} fill="#ff9f1c" stroke={INK} strokeWidth={3} />
						<ellipse cx={x + 2} cy={y - 10} rx={4} ry={2} fill="#52b788" />
					</g>
				))}
				<rect x={22} y={84} width={130} height={44} rx={6} fill="#f8f4ea" stroke={INK} strokeWidth={4} />
				<line x1={22} y1={100} x2={152} y2={100} stroke={INK} strokeWidth={2.5} />
				<path d="M150 44 H196 Q214 44 216 62 L220 128 H150 Z" fill="#f8f4ea" stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M160 54 H196 Q204 54 206 64 L208 86 H160 Z" fill={GLASS} stroke={INK} strokeWidth={3.5} />
				<Face eyes={[[176, 70], [196, 70]]} r={6} mouth={[188, 108]} cheeks={[[166, 108], [210, 106]]} blink={blink} />
				<Wheel x={64} y={134} r={19} spin={spin} />
				<Wheel x={186} y={134} r={19} spin={spin} />
			</>
		),
	},
	// 8. classic taxi
	{
		label: 'タクシー', color: '#ffbe0b',
		sil: <><path d="M16 120 Q16 98 40 96 L64 94 L88 64 Q96 56 110 56 H158 Q172 56 180 68 L198 94 Q226 96 226 118 V124 Q226 132 216 132 H26 Q16 132 16 124 Z" /><rect x={110} y={38} width={44} height={20} rx={5} /><circle cx={64} cy={132} r={21} /><circle cx={180} cy={132} r={21} /></>,
		art: (spin, blink) => (
			<>
				<rect x={110} y={38} width={44} height={20} rx={5} fill="#fffbe6" stroke={INK} strokeWidth={3.5} />
				<text x={132} y={53} textAnchor="middle" fontSize={12} fontWeight={900} fill={INK} fontFamily="Arial, sans-serif">TAXI</text>
				<path d="M16 120 Q16 98 40 96 L64 94 L88 64 Q96 56 110 56 H158 Q172 56 180 68 L198 94 Q226 96 226 118 V124 Q226 132 216 132 H26 Q16 132 16 124 Z" fill="#ffd23f" stroke={INK} strokeWidth={4} strokeLinejoin="round" />
				<path d="M92 92 L106 66 H130 V92 Z" fill={GLASS} stroke={INK} strokeWidth={3.5} strokeLinejoin="round" />
				<path d="M136 66 H158 Q166 66 172 74 L184 92 H136 Z" fill={GLASS} stroke={INK} strokeWidth={3.5} strokeLinejoin="round" />
				{Array.from({length: 10}).map((_, i) => <rect key={i} x={30 + i * 18} y={104} width={9} height={8} fill={i % 2 ? '#fffbe6' : INK} />)}
				<circle cx={216} cy={106} r={6} fill="#fffbe6" stroke={INK} strokeWidth={3} />
				<Face eyes={[[152, 80], [170, 80]]} r={5.5} mouth={[176, 122]} cheeks={[[150, 122], [204, 118]]} blink={blink} />
				<Wheel x={64} y={132} r={19} spin={spin} />
				<Wheel x={180} y={132} r={19} spin={spin} />
			</>
		),
	},
];

/** Sticker slots inside the picture (centre, fractions of the full frame), away from captions, HUD and callouts. */
const SLOTS: [number, number][] = [[0.87, 0.2], [0.13, 0.72], [0.87, 0.73], [0.13, 0.3]];

const Sparkle: React.FC<{x: number; y: number; s: number; color: string}> = ({x, y, s, color}) => (
	<path d={`M${x} ${y - s} Q${x} ${y} ${x + s} ${y} Q${x} ${y} ${x} ${y + s} Q${x} ${y} ${x - s} ${y} Q${x} ${y} ${x} ${y - s} Z`} fill={color} />
);

const Sticker: React.FC<{idx: number; born: number; dies: number | null}> = ({idx, born, dies}) => {
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const car = CARS[idx % CARS.length];
	const t = f - born;
	const pop = spring({frame: t, fps, config: {damping: 9, stiffness: 140, mass: 0.8}});
	const out = dies == null ? 0 : clamp((f - dies) / 12, 0, 1);
	const scale = pop * (1 - out);
	if (scale <= 0.001) return null;
	const [sx, sy] = SLOTS[idx % SLOTS.length];
	const w = W * 0.13;
	const tilt = (idx % 2 ? 7 : -7) + Math.sin((f / fps) * 2.4 + idx) * 3 + (1 - pop) * (idx % 2 ? 40 : -40);
	const bob = Math.sin((f / fps) * Math.PI * 1.2 + idx * 1.7) * H * 0.006;
	const cyc = (t + idx * 37) % 130; // blink every ~4 s
	const blink = cyc < 5 ? Math.abs(cyc - 2.5) / 2.5 * 0.9 + 0.1 : 1;
	const spin = f * 9;
	const body = font('Rajdhani');
	const tw = Math.sin(f * 0.25 + idx) * 0.5 + 0.5;
	return (
		<div
			style={{
				position: 'absolute',
				left: sx * W - w / 2,
				top: sy * H - (w * 0.75) / 2 + bob,
				width: w,
				transform: `scale(${scale}) rotate(${tilt}deg)`,
				filter: 'drop-shadow(0 6px 10px rgba(0,0,0,0.45))',
			}}
		>
			<svg viewBox="-10 0 260 175" width={w} height={w * 0.68}>
				<g fill="#fff" stroke="#fff" strokeWidth={18} strokeLinejoin="round">{car.sil}</g>
				{car.art(spin, blink)}
				<Sparkle x={8} y={22} s={9 + 4 * tw} color="#fff6a5" />
				<Sparkle x={236} y={30} s={7 + 4 * (1 - tw)} color="#ffffff" />
			</svg>
			<div style={{display: 'flex', justifyContent: 'center', marginTop: -w * 0.02}}>
				<div
					style={{
						background: car.color,
						color: '#fff',
						fontFamily: body,
						fontWeight: 800,
						fontSize: w * 0.12,
						padding: `${w * 0.012}px ${w * 0.07}px`,
						borderRadius: w,
						border: `${w * 0.022}px solid #fff`,
						WebkitTextStroke: `${w * 0.008}px ${INK}`,
						letterSpacing: '0.04em',
						whiteSpace: 'nowrap',
					}}
				>
					{car.label}
				</div>
			</div>
		</div>
	);
};

export const Stickers: React.FC<{m: Manifest; decor: Decor}> = ({m, decor}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const every = Math.max(5, decor.stickerEvery ?? 60) * fps;
	const keep = decor.maxStickers ?? 3;
	const end = m.chapters?.find((c) => c.hidden)?.from ?? m.durationInFrames; // leave the end screen clear
	const n = Math.floor(Math.min(f, end - 1) / every) + 1;
	const items: React.ReactNode[] = [];
	for (let i = Math.max(0, n - keep - 1); i < n; i++) {
		const born = i * every + 6;
		const replaced = i + keep < n ? (i + keep) * every + 6 : null;
		const dies = replaced ?? (f >= end ? end : null);
		items.push(<Sticker key={i} idx={i} born={born} dies={dies} />);
	}
	return <AbsoluteFill style={{pointerEvents: 'none'}}>{items}</AbsoluteFill>;
};

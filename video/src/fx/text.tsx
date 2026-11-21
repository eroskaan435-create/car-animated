import React from 'react';
import {interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp, easeOut, hexA} from '../util';

export const chrome = (accent: string): React.CSSProperties => ({
	backgroundImage: `linear-gradient(180deg, #ffffff 0%, #ffffff 42%, ${hexA(accent, 0.9)} 50%, #d9d9d9 58%, #ffffff 100%)`,
	WebkitBackgroundClip: 'text',
	backgroundClip: 'text',
	color: 'transparent',
});

/** Words slam in one after another (scale down + blur -> sharp). */
export const SlamWords: React.FC<{
	text: string;
	start?: number;
	stagger?: number;
	style?: React.CSSProperties;
	wordStyle?: React.CSSProperties;
	from?: number;
}> = ({text, start = 0, stagger = 4, style, wordStyle, from = 2.4}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const words = text.split(/\s+/).filter(Boolean);
	return (
		<div style={style}>
			{words.map((w, i) => {
				const sp = spring({frame: frame - start - i * stagger, fps, config: {damping: 13, mass: 0.55, stiffness: 190}});
				const sc = interpolate(sp, [0, 1], [from, 1]);
				return (
					<span
						key={i}
						style={{
							display: 'inline-block',
							marginRight: '0.22em',
							transform: `scale(${sc})`,
							opacity: clamp(sp * 3, 0, 1),
							filter: sp < 0.98 ? `blur(${(1 - sp) * 14}px)` : undefined,
							...wordStyle,
						}}
					>
						{w}
					</span>
				);
			})}
		</div>
	);
};

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*@';

/** Decode/scramble reveal, letter by letter. */
export const ScrambleText: React.FC<{text: string; start?: number; duration?: number; style?: React.CSSProperties}> = ({
	text,
	start = 0,
	duration = 14,
	style,
}) => {
	const frame = useCurrentFrame() - start;
	if (frame < 0) return null;
	const chars = text.split('').map((c, i) => {
		if (c === ' ') return ' ';
		const revealAt = (i / Math.max(1, text.length)) * duration + random(`sc-${text}-${i}`) * 4;
		if (frame >= revealAt) return c;
		return GLYPHS[Math.floor(random(`g-${i}-${frame}`) * GLYPHS.length)];
	});
	const flicker = frame < duration + 4 && random(`fl-${frame}`) > 0.8 ? 0.45 : 1;
	return <div style={{...style, opacity: flicker}}>{chars.join('')}</div>;
};

/** Parses "640 HP", "$189,900", "2.6 s" and counts up to the value. */
export const Counter: React.FC<{value: string; start: number; duration?: number; from?: number}> = ({
	value,
	start,
	duration = 18,
	from = 0,
}) => {
	const frame = useCurrentFrame();
	const m = value.match(/^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$/);
	if (!m) return <>{value}</>;
	const [, pre, num, post] = m;
	const target = parseFloat(num.replace(/,/g, ''));
	const decimals = num.includes('.') ? num.split('.')[1].length : 0;
	const p = easeOut(clamp((frame - start) / duration, 0, 1));
	const v = from * target + (target - from * target) * p;
	const str = num.includes(',')
		? v.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals})
		: v.toFixed(decimals);
	return (
		<>
			{pre}
			<span style={{fontVariantNumeric: 'tabular-nums'}}>{str}</span>
			{post}
		</>
	);
};

/** Skewed caption tag that slides in from the left. */
export const Caption: React.FC<{
	text: string;
	start: number;
	end: number;
	accent: string;
	font: string;
	size: number;
	style?: React.CSSProperties;
}> = ({text, start, end, accent, font, size, style}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	if (!text) return null;
	const inP = spring({frame: frame - start, fps, config: {damping: 16, stiffness: 160}});
	const outP = clamp((frame - (end - 6)) / 6, 0, 1);
	const x = interpolate(inP, [0, 1], [-110, 0]) - outP * 120;
	return (
		<div style={{position: 'absolute', overflow: 'hidden', ...style}}>
			<div
				style={{
					transform: `translateX(${x}%) skewX(-12deg)`,
					background: accent,
					padding: `${size * 0.22}px ${size * 0.6}px`,
					boxShadow: `0 0 ${size}px ${hexA(accent, 0.6)}`,
				}}
			>
				<div
					style={{
						transform: 'skewX(12deg)',
						fontFamily: font,
						fontSize: size,
						fontWeight: 700,
						color: '#fff',
						letterSpacing: '0.06em',
						textTransform: 'uppercase',
						whiteSpace: 'nowrap',
					}}
				>
					{text}
				</div>
			</div>
		</div>
	);
};

import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {font} from '../fonts';
import type {Manifest} from '../types';
import {clamp, hexA, unit} from '../util';
import {Counter} from './text';

const FULLSCREEN = new Set(['intro', 'hero', 'chapter', 'proscons', 'endscreen']);

/** Long-form overlays: chapter HUD, progress bar, spec callouts and burned-in captions. */
export const LongOverlays: React.FC<{m: Manifest}> = ({m}) => {
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const S = unit(W, H);
	const {theme} = m;
	const body = font(theme.fontBody);
	const display = font(theme.fontDisplay);
	const chapters = (m.chapters ?? []).filter((c) => !c.hidden);
	// Hide overlays while a full-screen graphic scene is on top.
	const top = [...m.scenes].reverse().find((s) => f >= s.from && f < s.from + s.duration);
	const covered = !top || FULLSCREEN.has(top.type);
	const body0 = chapters.find((c) => c.index === 1)?.from ?? 0;
	const end = m.chapters?.find((c) => c.hidden)?.from ?? m.durationInFrames;
	const cur = chapters.filter((c) => c.index > 0 && f >= c.from).pop();

	const cap = m.burnCaptions ? m.captions?.find((c) => f >= c.from && f < c.to) : undefined;
	const co = m.callouts?.find((c) => f >= c.from && f < c.to);

	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			{/* chapter label */}
			{!covered && cur && f < end ? (
				<div style={{position: 'absolute', left: W * 0.04, top: H * 0.05, display: 'flex', alignItems: 'stretch', fontFamily: body, fontWeight: 700}}>
					<div style={{background: theme.accent, color: '#fff', fontSize: 26 * S, padding: `${8 * S}px ${14 * S}px`, letterSpacing: '0.1em'}}>
						{String(cur.index).padStart(2, '0')}
					</div>
					<div style={{background: hexA('#000000', 0.55), color: '#fff', fontSize: 26 * S, padding: `${8 * S}px ${18 * S}px`, letterSpacing: '0.18em', textTransform: 'uppercase'}}>
						{cur.title}
					</div>
				</div>
			) : null}

			{/* progress bar split into chapters */}
			{f >= body0 && f < end && !covered ? (
				<div style={{position: 'absolute', left: W * 0.04, right: W * 0.04, bottom: H * 0.035, height: 6 * S, display: 'flex', gap: 6 * S}}>
					{chapters
						.filter((c) => c.index > 0)
						.map((c) => {
							const p = clamp((f - c.from) / Math.max(1, c.to - c.from), 0, 1);
							return (
								<div key={c.index} style={{flex: c.to - c.from, background: hexA('#ffffff', 0.25), borderRadius: 3 * S, overflow: 'hidden'}}>
									<div style={{width: `${p * 100}%`, height: '100%', background: theme.accent}} />
								</div>
							);
						})}
				</div>
			) : null}

			{/* spec callout */}
			{co && !covered ? <Callout key={co.from} co={co} f={f} W={W} H={H} S={S} fps={fps} accent={theme.accent} body={body} display={display} /> : null}

			{/* captions */}
			{cap && !covered ? (
				<div style={{position: 'absolute', left: 0, right: 0, bottom: H * 0.08, display: 'flex', justifyContent: 'center'}}>
					<div
						style={{
							maxWidth: W * 0.78,
							background: hexA('#000000', 0.62),
							borderRadius: 10 * S,
							padding: `${10 * S}px ${22 * S}px`,
							fontFamily: body,
							fontWeight: 700,
							fontSize: 46 * S,
							lineHeight: 1.25,
							color: '#fff',
							textAlign: 'center',
						}}
					>
						{cap.text}
					</div>
				</div>
			) : null}
		</AbsoluteFill>
	);
};

const Callout: React.FC<{
	co: {from: number; to: number; label: string; value: string};
	f: number;
	W: number;
	H: number;
	S: number;
	fps: number;
	accent: string;
	body: string;
	display: string;
}> = ({co, f, W, H, S, fps, accent, body, display}) => {
	const sp = spring({frame: f - co.from, fps, config: {damping: 15, stiffness: 160}});
	const out = clamp((f - (co.to - 10)) / 10, 0, 1);
	return (
		<div
			style={{
				position: 'absolute',
				right: W * 0.04,
				top: H * 0.36,
				minWidth: W * 0.22,
				transform: `translateX(${((1 - sp) + out) * 120}%)`,
				background: `linear-gradient(135deg, ${hexA('#000000', 0.75)}, ${hexA('#000000', 0.55)})`,
				borderRight: `${8 * S}px solid ${accent}`,
				borderRadius: 14 * S,
				padding: `${18 * S}px ${28 * S}px`,
				boxShadow: `0 0 ${40 * S}px ${hexA(accent, 0.35)}`,
				textAlign: 'right',
			}}
		>
			<div style={{fontFamily: body, fontWeight: 700, fontSize: 26 * S, letterSpacing: '0.2em', color: accent, textTransform: 'uppercase'}}>{co.label}</div>
			<div style={{fontFamily: display, fontWeight: 800, fontSize: 66 * S, color: '#fff', lineHeight: 1.05, whiteSpace: 'nowrap'}}>
				<Counter value={co.value} start={co.from} duration={18} />
			</div>
		</div>
	);
};

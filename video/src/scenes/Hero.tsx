import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, fontRatio} from '../fonts';
import {Particles} from '../fx/fx';
import {Photo} from '../fx/layers';
import {chrome, ScrambleText, SlamWords} from '../fx/text';
import type {Scene} from '../types';
import {clamp, easeInOut, fitFont, visLen, frameImage, hexA, lerp, splitTitle, unit, useManifest} from '../util';

export const Hero: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H} = useVideoConfig();
	const S = unit(W, H);
	const {theme, car} = m;
	const B = m.beatFrames;
	const D = scene.duration;
	const img = m.images[scene.image ?? 0];
	const p = f / D;
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);
	const cues = scene.cues ?? {};

	const framed = frameImage(img, W, H, 'car', 1 + 0.1 * easeInOut(p));
	const hasCut = !!img.cutout;
	const [, y0, , y1] = img.box;
	const carTop = framed.top + y0 * framed.dh;
	const carH = (y1 - y0) * framed.dh;
	const carBottom = carTop + carH;

	const lines = splitTitle((car.title || car.tagline).toUpperCase());
	const maxLen = Math.max(...lines.map((l) => visLen(l, fontRatio(theme.fontDisplay))));
	const fs = Math.min(fitFont(maxLen, W * 0.94, fontRatio(theme.fontDisplay)), H * 0.24, (hasCut ? 0.75 : 0.5) * H / lines.length);
	const blockH = lines.length * fs * 0.95;
	const top = hasCut ? clamp(carTop + carH * 0.2 - blockH, H * 0.05, H * 0.6) : clamp(carTop - blockH - 30 * S, H * 0.06, H * 0.5);

	const title = (
		<div style={{position: 'absolute', left: 0, right: 0, top, textAlign: 'center'}}>
			{lines.map((l, i) => (
				<SlamWords
					key={i}
					text={l}
					start={(cues.title ?? 0) + i * 3}
					stagger={3}
					style={{
						fontFamily: display,
						fontWeight: 800,
						fontSize: fs,
						lineHeight: 0.95,
						whiteSpace: 'nowrap',
						filter: `drop-shadow(0 ${6 * S}px ${24 * S}px rgba(0,0,0,0.6))`,
					}}
					wordStyle={chrome(theme.accent)}
				/>
			))}
		</div>
	);

	const sweepStart = (cues.subtitle ?? B * 2) - 4;
	const sweep = theme.fx.lightSweep ? (f - sweepStart) / 26 : 0;
	const subTop = Math.min(carBottom + 34 * S, H * 0.9);

	return (
		<AbsoluteFill>
			<Photo
				img={img}
				framed={framed}
				depthOffset={hasCut ? null : [lerp(-0.02, 0.02, easeInOut(p)), 0]}
				behind={hasCut ? title : null}
				cutoutOnTop={hasCut}
				sweep={sweep}
				sweepColor={theme.accent2}
			/>
			{!hasCut ? (
				<>
					<AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.55), transparent 45%)'}} />
					{title}
				</>
			) : null}
			<Particles kind={theme.fx.particles} accent={theme.accent} seed="hero" intensity={0.8} />
			<div style={{position: 'absolute', left: 0, right: 0, top: subTop, display: 'flex', justifyContent: 'center'}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 18 * S}}>
					<div style={{height: 4 * S, width: 60 * S * clamp((f - (cues.subtitle ?? B * 2)) / 8, 0, 1), background: theme.accent}} />
					<ScrambleText
						text={car.tagline.toUpperCase()}
						start={cues.subtitle ?? B * 2}
						duration={12}
						style={{
							fontFamily: body,
							fontWeight: 700,
							fontSize: 34 * S,
							letterSpacing: '0.3em',
							color: '#fff',
							textShadow: `0 0 ${16 * S}px ${hexA(theme.accent, 0.9)}`,
						}}
					/>
					<div style={{height: 4 * S, width: 60 * S * clamp((f - (cues.subtitle ?? B * 2)) / 8, 0, 1), background: theme.accent}} />
				</div>
			</div>
		</AbsoluteFill>
	);
};

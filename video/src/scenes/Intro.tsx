import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, fontRatio} from '../fonts';
import {Distort, Particles, Streaks} from '../fx/fx';
import {chrome, ScrambleText} from '../fx/text';
import type {Scene} from '../types';
import {clamp, easeOut, fitFont, frameImage, hexA, splitTitle, unit, useManifest} from '../util';

export const Intro: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H} = useVideoConfig();
	const S = unit(W, H);
	const {theme, car, images} = m;
	const B = m.beatFrames;
	const D = scene.duration;
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);
	const cues = scene.cues ?? {};
	const tTitle: number = cues.title ?? B * 2;
	const teasers: {frame: number; image: number}[] = cues.teasers ?? [];

	const lines = splitTitle((car.title || car.tagline).toUpperCase());
	const maxLen = Math.max(...lines.map((l) => l.length));
	const fs = Math.min(fitFont(maxLen, W * 0.88, fontRatio(theme.fontDisplay)), H * 0.2);
	const wipe = easeOut(clamp((f - tTitle) / 10, 0, 1));
	const titleScale = 1 + 0.08 * clamp((f - tTitle) / (D - tTitle), 0, 1);

	const teaser = teasers.find((t) => f >= t.frame && f < t.frame + 5);
	const white = clamp((f - (D - 7)) / 7, 0, 1);

	return (
		<AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 55%, ${hexA(theme.accent, 0.22)} 0%, ${theme.bg} 55%, #000 100%)`}}>
			<Streaks accent={theme.accent} accent2={theme.accent2} speed={1 + f / D} />
			<Particles kind={theme.fx.particles} accent={theme.accent} seed="intro" intensity={0.7} />

			<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', flexDirection: 'column'}}>
				<ScrambleText
					text={car.tagline.toUpperCase()}
					start={cues.tagline ?? 0}
					duration={Math.min(18, tTitle)}
					style={{
						fontFamily: body,
						fontWeight: 700,
						fontSize: 38 * S,
						letterSpacing: `${interpolate(f, [0, D], [0.5, 0.3])}em`,
						color: theme.accent2,
						textShadow: `0 0 ${20 * S}px ${theme.accent}`,
						transform: `translateY(${f >= tTitle ? -fs * 0.35 * wipe : 0}px)`,
						marginBottom: 24 * S,
						textAlign: 'center',
						padding: `0 ${40 * S}px`,
					}}
				/>
				{f >= tTitle ? (
					<div style={{transform: `scale(${titleScale})`, textAlign: 'center'}}>
						{lines.map((l, i) => (
							<div
								key={i}
								style={{
									fontFamily: display,
									fontWeight: 800,
									fontSize: fs,
									lineHeight: 0.95,
									...chrome(theme.accent),
									clipPath: `inset(0 ${100 - wipe * 100}% 0 0)`,
									filter: `drop-shadow(0 0 ${18 * S}px ${hexA(theme.accent, 0.8)})`,
								}}
							>
								{l}
							</div>
						))}
						<div
							style={{
								height: 6 * S,
								margin: `${18 * S}px auto 0`,
								width: `${wipe * 70}%`,
								background: `linear-gradient(90deg, transparent, ${theme.accent}, transparent)`,
							}}
						/>
					</div>
				) : null}
			</AbsoluteFill>

			{teaser ? Teaser({idx: teaser.image, t: f - teaser.frame}) : null}
			<AbsoluteFill style={{background: '#fff', opacity: white * theme.fx.flash}} />
		</AbsoluteFill>
	);

	function Teaser({idx, t}: {idx: number; t: number}) {
		const img = images[idx];
		const fr = frameImage(img, W, H, 'cover', 1.35 + t * 0.03);
		return (
			<AbsoluteFill>
				<Distort rgb={theme.fx.glitch ? (5 - t) * 4 * S : 0}>
					<Img
						src={staticFile(img.src)}
						style={{position: 'absolute', left: fr.left, top: fr.top, width: fr.dw, height: fr.dh, filter: 'contrast(1.3)'}}
					/>
				</Distort>
				<AbsoluteFill style={{background: hexA(theme.accent, 0.25), mixBlendMode: 'color'}} />
				<AbsoluteFill style={{background: '#fff', opacity: t === 0 ? 0.6 : 0}} />
			</AbsoluteFill>
		);
	}
};

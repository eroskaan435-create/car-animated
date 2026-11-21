import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, fontRatio} from '../fonts';
import {Particles, Shockwave, SpeedLines} from '../fx/fx';
import {Photo} from '../fx/layers';
import {chrome, Counter} from '../fx/text';
import type {Scene} from '../types';
import {clamp, fitFont, frameImage, hexA, unit, useManifest} from '../util';

export const Price: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const S = unit(W, H);
	const {theme, car} = m;
	const D = scene.duration;
	const img = m.images[scene.image ?? 0];
	const slam = scene.cues?.slam ?? 0;
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);

	const framed = frameImage(img, W, H, 'cover', 1.3 + 0.12 * (f / D));
	const sp = spring({frame: f - slam, fps, config: {damping: 11, stiffness: 200, mass: 0.6}});
	const text = car.price || car.tagline;
	const fs = Math.min(fitFont(text.length, W * 0.88, fontRatio(theme.fontDisplay) * 1.05), H * 0.22);
	const bar = clamp((f - slam - 4) / 8, 0, 1);

	return (
		<AbsoluteFill>
			<Photo img={img} framed={framed} />
			<AbsoluteFill style={{background: `radial-gradient(ellipse at center, ${hexA(theme.accent, 0.35)} 0%, rgba(0,0,0,0.78) 65%)`}} />
			{theme.fx.speedLines ? <SpeedLines intensity={0.8} seed="price" /> : null}
			<Shockwave at={slam} color={theme.accent} />
			<Particles kind={theme.fx.particles === 'bokeh' ? 'bokeh' : 'sparks'} accent={theme.accent} burstAt={slam} seed="burst" />
			<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', flexDirection: 'column'}}>
				{car.price ? (
					<div
						style={{
							fontFamily: body,
							fontWeight: 700,
							fontSize: 40 * S,
							letterSpacing: '0.35em',
							color: theme.accent2,
							textTransform: 'uppercase',
							opacity: clamp(sp * 2, 0, 1),
							transform: `translateY(${(1 - sp) * -40 * S}px)`,
							marginBottom: 34 * S,
						}}
					>
						{car.priceLabel}
					</div>
				) : null}
				<div
					style={{
						fontFamily: display,
						fontWeight: 800,
						fontSize: fs,
						lineHeight: 1,
						whiteSpace: 'nowrap',
						transform: `scale(${interpolate(sp, [0, 1], [2.3, 1])})`,
						opacity: clamp(sp * 3, 0, 1),
						filter: `drop-shadow(0 0 ${30 * S}px ${hexA(theme.accent, 0.85)})`,
					}}
				>
					<span style={chrome(theme.accent)}>{car.price ? <Counter value={text} start={slam} duration={12} from={0.55} /> : text}</span>
				</div>
				<div style={{height: 8 * S, width: W * 0.6 * bar, marginTop: 20 * S, background: `linear-gradient(90deg, transparent, ${theme.accent}, transparent)`}} />
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

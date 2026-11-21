import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, fontRatio} from '../fonts';
import {Particles} from '../fx/fx';
import {Photo} from '../fx/layers';
import {chrome, SlamWords} from '../fx/text';
import type {Scene} from '../types';
import {clamp, fitFont, frameImage, hexA, unit, useManifest} from '../util';

export const Outro: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const S = unit(W, H);
	const {theme, car} = m;
	const B = m.beatFrames;
	const D = scene.duration;
	const img = m.images[scene.image ?? 0];
	const cues = scene.cues ?? {};
	const ctaAt: number = cues.cta ?? B * 2;
	const finalAt: number = cues.final ?? D - B * 3;
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);
	const vertical = H > W * 1.1;

	const framed = frameImage(img, W, H, vertical ? 'car' : 'cover', 1.04 + 0.1 * (f / D));
	const cta = spring({frame: f - ctaAt, fps, config: {damping: 12, stiffness: 180}});
	const bump = 1 + 0.06 * Math.exp(-Math.max(0, f - finalAt) / 5) * (f >= finalAt ? 1 : 0);
	const beatGlow = f < ctaAt ? 0 : Math.exp(-((f - ctaAt) % B) / 4);
	const fadeOut = clamp((f - (D - 12)) / 12, 0, 1);
	const brand = car.dealer || '';
	const titleFs = Math.min(fitFont(car.title.length, W * 0.9, fontRatio(theme.fontDisplay)), 110 * S);

	return (
		<AbsoluteFill>
			<Photo img={img} framed={framed} />
			<AbsoluteFill style={{background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.35) 45%, rgba(0,0,0,0.65) 100%)'}} />
			<Particles kind={theme.fx.particles} accent={theme.accent} seed="outro" intensity={0.7} />

			<AbsoluteFill style={{transform: `scale(${bump})`}}>
				{/* brand */}
				<div style={{position: 'absolute', top: H * 0.07, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
					{car.logo ? (
						<Img
							src={staticFile(car.logo)}
							style={{maxWidth: W * 0.5, maxHeight: H * 0.12, objectFit: 'contain', opacity: clamp(f / 10, 0, 1)}}
						/>
					) : brand ? (
						<SlamWords
							text={brand.toUpperCase()}
							start={2}
							stagger={3}
							style={{fontFamily: display, fontWeight: 800, fontSize: 84 * S, letterSpacing: '0.06em', color: '#fff', textAlign: 'center'}}
							wordStyle={chrome(theme.accent)}
						/>
					) : null}
				</div>

				{/* title + CTA */}
				<div
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						bottom: H * (vertical ? 0.12 : 0.1),
						display: 'flex',
						flexDirection: 'column',
						alignItems: 'center',
						gap: 26 * S,
					}}
				>
					<div
						style={{
							fontFamily: display,
							fontWeight: 800,
							fontSize: titleFs,
							color: '#fff',
							textTransform: 'uppercase',
							textAlign: 'center',
							lineHeight: 1,
							opacity: clamp((f - 4) / 8, 0, 1),
							textShadow: `0 0 ${24 * S}px ${hexA(theme.accent, 0.7)}`,
						}}
					>
						{car.title}
					</div>
					<div
						style={{
							transform: `scale(${interpolate(cta, [0, 1], [0.4, 1])})`,
							opacity: clamp(cta * 2, 0, 1),
							background: `linear-gradient(135deg, ${theme.accent}, ${theme.accent2})`,
							borderRadius: 999,
							padding: `${22 * S}px ${64 * S}px`,
							boxShadow: `0 0 ${(30 + 50 * beatGlow) * S}px ${hexA(theme.accent, 0.5 + 0.4 * beatGlow)}`,
							fontFamily: body,
							fontWeight: 800,
							fontSize: 44 * S,
							letterSpacing: '0.12em',
							color: '#fff',
							textTransform: 'uppercase',
							whiteSpace: 'nowrap',
						}}
					>
						{car.cta}
					</div>
					{car.contact ? (
						<div
							style={{
								fontFamily: body,
								fontWeight: 600,
								fontSize: 34 * S,
								color: hexA('#ffffff', 0.9),
								letterSpacing: '0.08em',
								opacity: clamp((f - ctaAt - 6) / 8, 0, 1),
								textAlign: 'center',
								padding: `0 ${40 * S}px`,
							}}
						>
							{car.contact}
						</div>
					) : null}
				</div>
			</AbsoluteFill>
			<AbsoluteFill style={{background: '#000', opacity: fadeOut}} />
		</AbsoluteFill>
	);
};

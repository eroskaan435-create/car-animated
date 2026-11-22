import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, fontRatio} from '../fonts';
import {Particles} from '../fx/fx';
import {BlurBg, Photo} from '../fx/layers';
import {chrome, ScrambleText, SlamWords} from '../fx/text';
import type {Scene} from '../types';
import {clamp, easeOut, fitFont, visLen, frameImage, hexA, unit, useManifest} from '../util';

/** Animated chapter title card: big outlined number + slammed title. */
export const ChapterCard: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H} = useVideoConfig();
	const S = unit(W, H);
	const {theme} = m;
	const img = m.images[scene.image ?? 0];
	const idx: number = scene.cues?.index ?? 1;
	const title: string = (scene.cues?.title ?? '').toUpperCase();
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);
	const wipe = easeOut(clamp((f - 4) / 12, 0, 1));
	const fs = Math.min(fitFont(visLen(title, fontRatio(theme.fontDisplay)), W * 0.62, fontRatio(theme.fontDisplay)), 150 * S);
	const framed = frameImage(img, W, H, 'cover', 1.15 + 0.08 * (f / scene.duration));
	return (
		<AbsoluteFill style={{background: theme.bg}}>
			<div style={{position: 'absolute', inset: 0, opacity: 0.35}}>
				<Photo img={img} framed={framed} />
			</div>
			<AbsoluteFill style={{background: `linear-gradient(90deg, ${theme.bg} 15%, ${hexA(theme.bg, 0.6)} 55%, ${hexA(theme.accent, 0.25)} 100%)`}} />
			<Particles kind={theme.fx.particles} accent={theme.accent} seed={`ch${idx}`} intensity={0.6} />
			<div
				style={{
					position: 'absolute',
					left: W * 0.06,
					top: H * 0.5,
					transform: `translateY(-50%) translateX(${(1 - wipe) * -80 * S}px)`,
					fontFamily: display,
					fontWeight: 800,
					fontSize: 420 * S,
					lineHeight: 1,
					color: 'transparent',
					WebkitTextStroke: `${3 * S}px ${hexA(theme.accent, 0.8)}`,
					opacity: 0.55 * wipe,
				}}
			>
				{String(idx).padStart(2, '0')}
			</div>
			<div style={{position: 'absolute', left: W * 0.3, right: W * 0.05, top: H * 0.5, transform: 'translateY(-50%)'}}>
				<ScrambleText
					text={`CHAPTER ${String(idx).padStart(2, '0')}`}
					start={2}
					duration={10}
					style={{fontFamily: body, fontWeight: 700, fontSize: 34 * S, letterSpacing: '0.45em', color: theme.accent}}
				/>
				<SlamWords
					text={title}
					start={6}
					stagger={3}
					style={{fontFamily: display, fontWeight: 800, fontSize: fs, lineHeight: 1.02, marginTop: 10 * S}}
					wordStyle={chrome(theme.accent)}
				/>
				<div style={{height: 6 * S, width: `${wipe * 60}%`, marginTop: 20 * S, background: `linear-gradient(90deg, ${theme.accent}, transparent)`}} />
			</div>
		</AbsoluteFill>
	);
};

/** Verdict pros / cons board. */
export const ProsCons: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const S = unit(W, H);
	const {theme} = m;
	const pros: string[] = scene.cues?.pros ?? [];
	const cons: string[] = scene.cues?.cons ?? [];
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);
	const img = m.images[scene.image ?? 0];

	const col = (title: string, items: string[], offset: number, good: boolean, x: number) => (
		<div style={{position: 'absolute', left: x, top: H * 0.2, width: W * 0.4}}>
			<div style={{fontFamily: display, fontWeight: 800, fontSize: 72 * S, color: good ? theme.accent : '#cfd3dc', letterSpacing: '0.05em'}}>{title}</div>
			{items.map((it, i) => {
				const at = 30 + 50 * (offset + i);
				const sp = spring({frame: f - at, fps, config: {damping: 14, stiffness: 170}});
				return (
					<div
						key={i}
						style={{
							display: 'flex',
							alignItems: 'center',
							gap: 22 * S,
							marginTop: 22 * S,
							opacity: clamp(sp * 2, 0, 1),
							transform: `translateX(${(1 - sp) * (good ? -60 : 60) * S}px)`,
							background: hexA('#ffffff', 0.06),
							borderLeft: `${6 * S}px solid ${good ? theme.accent : '#8a8f9c'}`,
							borderRadius: 12 * S,
							padding: `${16 * S}px ${22 * S}px`,
						}}
					>
						<div style={{fontSize: 40 * S, fontWeight: 900, color: good ? theme.accent : '#9aa0ad', fontFamily: body, width: 40 * S}}>{good ? '✓' : '✕'}</div>
						<div style={{fontFamily: body, fontWeight: 700, fontSize: 40 * S, color: '#fff'}}>{it}</div>
					</div>
				);
			})}
		</div>
	);

	return (
		<AbsoluteFill style={{background: theme.bg}}>
			<BlurBg img={img} />
			<AbsoluteFill style={{background: hexA('#000000', 0.62)}} />
			<div style={{position: 'absolute', top: H * 0.06, left: 0, right: 0, textAlign: 'center', fontFamily: body, fontWeight: 700, fontSize: 36 * S, letterSpacing: '0.4em', color: theme.accent2}}>
				THE VERDICT
			</div>
			{col('PROS', pros, 0, true, W * 0.06)}
			{col('CONS', cons, pros.length, false, W * 0.54)}
		</AbsoluteFill>
	);
};

/** YouTube end screen: info on the left, empty slots on the right for end-screen elements. */
export const EndScreen: React.FC<{scene: Scene}> = ({scene}) => {
	const m = useManifest();
	const f = useCurrentFrame();
	const {width: W, height: H, fps} = useVideoConfig();
	const S = unit(W, H);
	const {theme, car} = m;
	const img = m.images[scene.image ?? 0];
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);
	const D = scene.duration;
	const sub = spring({frame: f - 40, fps, config: {damping: 12}});
	const clicked = f > 75;
	const cursor = interpolate(f, [45, 72], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const fadeOut = clamp((f - (D - 20)) / 20, 0, 1);
	const framed = frameImage(img, W, H, 'cover', 1.1 + 0.05 * (f / D));
	return (
		<AbsoluteFill style={{background: theme.bg}}>
			<div style={{position: 'absolute', inset: 0, opacity: 0.45}}>
				<Photo img={img} framed={framed} />
			</div>
			<AbsoluteFill style={{background: `linear-gradient(90deg, ${hexA('#000000', 0.9)} 0%, ${hexA('#000000', 0.7)} 50%, ${hexA('#000000', 0.5)} 100%)`}} />
			<div style={{position: 'absolute', left: W * 0.06, top: H * 0.16, width: W * 0.42, display: 'flex', flexDirection: 'column', gap: 26 * S}}>
				{car.logo ? (
					<Img src={staticFile(car.logo)} style={{maxWidth: W * 0.25, maxHeight: H * 0.14, objectFit: 'contain', objectPosition: 'left'}} />
				) : car.dealer ? (
					<SlamWords text={car.dealer.toUpperCase()} start={4} style={{fontFamily: display, fontWeight: 800, fontSize: 90 * S}} wordStyle={chrome(theme.accent)} />
				) : null}
				<div style={{fontFamily: display, fontWeight: 800, fontSize: 64 * S, color: '#fff', textTransform: 'uppercase', lineHeight: 1.05}}>{car.title}</div>
				<div
					style={{
						alignSelf: 'flex-start',
						background: `linear-gradient(135deg, ${theme.accent}, ${theme.accent2})`,
						borderRadius: 999,
						padding: `${18 * S}px ${48 * S}px`,
						fontFamily: body,
						fontWeight: 800,
						fontSize: 38 * S,
						letterSpacing: '0.1em',
						color: '#fff',
						textTransform: 'uppercase',
						boxShadow: `0 0 ${40 * S}px ${hexA(theme.accent, 0.6)}`,
					}}
				>
					{car.cta}
				</div>
				{car.contact ? <div style={{fontFamily: body, fontWeight: 600, fontSize: 34 * S, color: hexA('#ffffff', 0.9)}}>{car.contact}</div> : null}
				<div style={{display: 'flex', alignItems: 'center', gap: 20 * S, marginTop: 20 * S, transform: `scale(${interpolate(sub, [0, 1], [0.6, 1])})`, transformOrigin: 'left', opacity: clamp(sub * 2, 0, 1)}}>
					<div
						style={{
							background: clicked ? '#3a3a3a' : '#ff0000',
							color: '#fff',
							borderRadius: 10 * S,
							padding: `${16 * S}px ${34 * S}px`,
							fontFamily: 'Roboto, Arial, sans-serif',
							fontWeight: 700,
							fontSize: 34 * S,
							letterSpacing: '0.04em',
							transform: `scale(${f > 72 && f < 80 ? 0.92 : 1})`,
						}}
					>
						{clicked ? 'SUBSCRIBED ✓' : 'SUBSCRIBE'}
					</div>
					<div style={{fontSize: 46 * S, transform: `rotate(${clicked ? Math.sin(f * 0.8) * 18 * Math.exp(-(f - 75) / 15) : 0}deg)`}}>🔔</div>
				</div>
			</div>
			{/* pointer animating to the subscribe button */}
			<div
				style={{
					position: 'absolute',
					left: W * 0.06 + 160 * S + cursor * 300 * S,
					top: H * 0.16 + 520 * S + cursor * 200 * S,
					width: 0,
					height: 0,
					opacity: f > 40 && f < 100 ? 1 : 0,
					borderLeft: `${18 * S}px solid transparent`,
					borderRight: `${18 * S}px solid transparent`,
					borderBottom: `${40 * S}px solid #fff`,
					transform: 'rotate(-30deg)',
					filter: 'drop-shadow(0 4px 8px rgba(0,0,0,.6))',
				}}
			/>
			{/* slots for YouTube end-screen video elements */}
			{[0, 1].map((i) => (
				<div
					key={i}
					style={{
						position: 'absolute',
						right: W * 0.06,
						top: H * (0.14 + i * 0.38),
						width: W * 0.36,
						height: W * 0.36 * (9 / 16),
						border: `${2 * S}px solid ${hexA(theme.accent, 0.6)}`,
						borderRadius: 14 * S,
						background: hexA('#000000', 0.35),
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						fontFamily: body,
						fontWeight: 700,
						fontSize: 30 * S,
						letterSpacing: '0.3em',
						color: hexA('#ffffff', 0.5),
						opacity: clamp((f - 10 - i * 8) / 12, 0, 1),
					}}
				>
					{i === 0 ? 'WATCH NEXT' : 'MORE REVIEWS'}
				</div>
			))}
			<AbsoluteFill style={{background: '#000', opacity: fadeOut}} />
		</AbsoluteFill>
	);
};

import React from 'react';
import {AbsoluteFill, Html5Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Grain, Vignette} from './fx/fx';
import {FRAME_SCALE, SizzleFrame, Stickers} from './fx/decor';
import {LongOverlays} from './fx/overlays';
import {TransitionWrap} from './fx/layers';
import {Hero} from './scenes/Hero';
import {Intro} from './scenes/Intro';
import {ChapterCard, EndScreen, ProsCons} from './scenes/Long';
import {Outro} from './scenes/Outro';
import {Price} from './scenes/Price';
import {Shot} from './scenes/Shot';
import {Specs} from './scenes/Specs';
import type {Manifest, Scene} from './types';
import {ManifestContext, noise1, unit} from './util';

const SceneView: React.FC<{scene: Scene}> = ({scene}) => {
	switch (scene.type) {
		case 'intro':
			return <Intro scene={scene} />;
		case 'hero':
			return <Hero scene={scene} />;
		case 'specs':
			return <Specs scene={scene} />;
		case 'price':
			return <Price scene={scene} />;
		case 'outro':
			return <Outro scene={scene} />;
		case 'chapter':
			return <ChapterCard scene={scene} />;
		case 'proscons':
			return <ProsCons scene={scene} />;
		case 'endscreen':
			return <EndScreen scene={scene} />;
		default:
			return <Shot scene={scene} />;
	}
};

/** Camera shake + beat pulse, driven by the same events as the soundtrack. */
function useCamera(m: Manifest) {
	const f = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const S = unit(width, height);
	let amp = 0;
	let flash = 0;
	for (const e of m.events) {
		const t = f - e.frame;
		if (t < 0 || t > 24) continue;
		const s = e.strength ?? 1;
		if (e.type === 'impact') {
			amp += 30 * S * s * m.theme.fx.shake * Math.exp(-t / 5);
			flash = Math.max(flash, s * Math.exp(-t / 3.2));
		}
	}
	for (const sc of m.scenes) {
		const t = f - sc.from;
		if (sc.transitionIn === 'flash' && t >= 0 && t < 12) flash = Math.max(flash, 0.75 * Math.exp(-t / 2.6));
	}
	const hero = m.scenes.find((s) => s.type === 'hero');
	let pulse = 0;
	if (hero && f >= hero.from && f < (m.pulseUntil ?? Infinity) && m.theme.fx.beatPulse > 0) {
		const ph = (f - hero.from) % m.beatFrames;
		pulse = m.theme.fx.beatPulse * Math.exp(-ph / 3);
	}
	const x = noise1('sx', f * 0.9) * amp;
	const y = noise1('sy', f * 0.9) * amp;
	const rot = noise1('sr', f * 0.7) * amp * 0.02;
	const scale = 1 + pulse + (amp > 0.5 ? (amp * 2.5) / width : 0);
	return {transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${scale})`, flash: flash * m.theme.fx.flash};
}

export const CarAd: React.FC<Manifest> = (m) => {
	const cam = useCamera(m);
	const frame = useCurrentFrame();
	if (!m.scenes?.length) return <AbsoluteFill style={{background: '#000'}} />;
	return (
		<ManifestContext.Provider value={m}>
			<AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
				<AbsoluteFill style={{transform: m.decor?.frame ? `scale(${FRAME_SCALE})` : undefined, overflow: 'hidden'}}>
				<AbsoluteFill style={{transform: cam.transform}}>
					{m.scenes.map((s, i) => frame < s.from - 30 || frame > s.from + s.duration ? null : (
						<Sequence key={i} from={s.from} durationInFrames={s.duration} premountFor={15} name={`${s.type}${s.move ? `:${s.move}` : ''}`}>
							<TransitionWrap duration={s.duration} tin={s.transitionIn} tout={s.transitionOut}>
								<SceneView scene={s} />
							</TransitionWrap>
						</Sequence>
					))}
				</AbsoluteFill>
				<Vignette />
				<Grain src={m.grain} amount={m.theme.fx.grain} />
				{m.mode === 'long' ? <LongOverlays m={m} /> : null}
				</AbsoluteFill>
				{m.decor?.frame ? <SizzleFrame accent={m.theme.accent} accent2={m.theme.accent2} /> : null}
				{m.decor?.stickers ? <Stickers m={m} decor={m.decor} /> : null}
				<AbsoluteFill style={{background: '#fff', opacity: Math.min(1, cam.flash), pointerEvents: 'none'}} />
				{m.audio ? <Html5Audio src={staticFile(m.audio)} /> : null}
			</AbsoluteFill>
		</ManifestContext.Provider>
	);
};

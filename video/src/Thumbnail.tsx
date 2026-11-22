import React from 'react';
import {AbsoluteFill, Img, staticFile, useVideoConfig} from 'remotion';
import {font, fontRatio} from './fonts';
import type {Manifest} from './types';
import {fitFont, hexA, splitTitle, visLen} from './util';

/** 1280x720 YouTube thumbnail: huge title, car cut-out, badge + price. */
export const Thumbnail: React.FC<Manifest> = (m) => {
	const {width: W, height: H} = useVideoConfig();
	if (!m.images?.length) return <AbsoluteFill style={{background: '#000'}} />;
	const {theme, car} = m;
	const hero = m.scenes?.find((s) => s.type === 'hero')?.image ?? 0;
	const img = m.images[hero];
	const display = font(theme.fontDisplay);
	const body = font(theme.fontBody);
	const lines = splitTitle((m.thumbnail?.text || car.title).toUpperCase());
	const maxLen = Math.max(...lines.map((l) => visLen(l, fontRatio(theme.fontDisplay))));
	const fs = Math.min(fitFont(maxLen, W * 0.55, fontRatio(theme.fontDisplay)), (H * 0.62) / lines.length);

	const [x0, y0, x1, y1] = img.box;
	const targetW = W * 0.72;
	const s = targetW / ((x1 - x0) * img.w);
	const dw = img.w * s;
	const dh = img.h * s;
	const left = W * 0.62 - ((x0 + x1) / 2) * dw;
	const top = H * 0.93 - y1 * dh;

	return (
		<AbsoluteFill style={{background: `radial-gradient(ellipse at 65% 60%, ${hexA(theme.accent, 0.55)} 0%, ${theme.bg} 60%, #000 100%)`, overflow: 'hidden'}}>
			{img.cutout ? (
				<>
					<Img src={staticFile(img.bg)} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0.35}} />
					<div style={{position: 'absolute', left: left + x0 * dw, width: (x1 - x0) * dw, top: H * 0.93 - 18, height: 36, borderRadius: '50%', background: 'radial-gradient(ellipse, rgba(0,0,0,.9), transparent 70%)'}} />
					<Img src={staticFile(img.cutout)} style={{position: 'absolute', left, top, width: dw, height: dh, filter: `drop-shadow(0 0 30px ${hexA(theme.accent, 0.6)})`}} />
				</>
			) : (
				<>
					<Img src={staticFile(img.src)} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'}} />
					<AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(0,0,0,.85) 0%, rgba(0,0,0,.4) 55%, transparent 80%)'}} />
				</>
			)}
			<div style={{position: 'absolute', left: W * 0.04, top: H * 0.08}}>
				{m.thumbnail?.badge ? (
					<div style={{display: 'inline-block', background: theme.accent, color: '#fff', fontFamily: body, fontWeight: 800, fontSize: 34, letterSpacing: '0.12em', padding: '8px 18px', transform: 'skewX(-10deg)', marginBottom: 14}}>
						{m.thumbnail.badge}
					</div>
				) : null}
				{lines.map((l, i) => (
					<div
						key={i}
						style={{
							fontFamily: display,
							fontWeight: 900,
							fontSize: fs,
							lineHeight: 0.98,
							color: i === lines.length - 1 ? theme.accent2 : '#fff',
							WebkitTextStroke: '3px #000',
							paintOrder: 'stroke fill',
							textShadow: `0 6px 0 #000, 0 0 40px ${hexA(theme.accent, 0.8)}`,
						}}
					>
						{l}
					</div>
				))}
			</div>
			{car.price ? (
				<div style={{position: 'absolute', left: W * 0.04, bottom: H * 0.07, background: '#fff', color: '#000', fontFamily: display, fontWeight: 900, fontSize: 52, padding: '6px 22px', borderRadius: 10, transform: 'rotate(-3deg)', boxShadow: `0 8px 0 ${theme.accent}`}}>
					{car.price}
				</div>
			) : null}
		</AbsoluteFill>
	);
};

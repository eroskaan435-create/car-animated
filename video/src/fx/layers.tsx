import React from 'react';
import {AbsoluteFill, Img, random, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {DepthImage} from '../three/DepthImage';
import type {ImageInfo, Transition} from '../types';
import {clamp, easeIn, easeOut, type Framed, unit} from '../util';
import {Distort, LightSweep} from './fx';

/** Blurred, darkened copy of the photo that fills the whole frame. */
export const BlurBg: React.FC<{img: ImageInfo; zoom?: number}> = ({img, zoom = 1.15}) => {
	const {width, height} = useVideoConfig();
	const s = Math.max(width / img.w, height / img.h) * zoom;
	return (
		<AbsoluteFill style={{overflow: 'hidden'}}>
			<Img
				src={staticFile(img.bg)}
				style={{
					position: 'absolute',
					width: img.w * s,
					height: img.h * s,
					left: (width - img.w * s) / 2,
					top: (height - img.h * s) / 2,
				}}
			/>
		</AbsoluteFill>
	);
};

const boxStyle = (f: Framed): React.CSSProperties => ({position: 'absolute', left: f.left, top: f.top, width: f.dw, height: f.dh});

/**
 * The photo, framed. Layers: blurred fill -> photo (or 3D depth photo) -> `behind`
 * (e.g. text that sits behind the car) -> car cutout -> light sweep.
 */
export const Photo: React.FC<{
	img: ImageInfo;
	framed: Framed;
	depthOffset?: [number, number] | null;
	behind?: React.ReactNode;
	cutoutOnTop?: boolean;
	sweep?: number;
	sweepColor?: string;
}> = ({img, framed, depthOffset, behind, cutoutOnTop, sweep = 0, sweepColor}) => {
	const {width, height} = useVideoConfig();
	const bandsV = framed.dh < height - 1;
	const bandsH = framed.dw < width - 1;
	const feather = bandsV
		? 'linear-gradient(to bottom, transparent 0%, #000 7%, #000 93%, transparent 100%)'
		: bandsH
			? 'linear-gradient(to right, transparent 0%, #000 7%, #000 93%, transparent 100%)'
			: undefined;
	return (
		<AbsoluteFill style={{overflow: 'hidden'}}>
			{bandsV || bandsH || depthOffset ? <BlurBg img={img} /> : null}
			{depthOffset && img.depth ? (
				<DepthImage img={img} framed={framed} W={width} H={height} offset={depthOffset} />
			) : (
				<Img src={staticFile(img.src)} style={{...boxStyle(framed), WebkitMaskImage: feather, maskImage: feather}} />
			)}
			{behind}
			{cutoutOnTop && img.cutout ? <Img src={staticFile(img.cutout)} style={boxStyle(framed)} /> : null}
			{sweep > 0 ? (
				<div style={boxStyle(framed)}>
					<LightSweep progress={sweep} mask={img.cutout} color={sweepColor} strength={img.cutout ? 0.9 : 0.35} />
				</div>
			) : null}
		</AbsoluteFill>
	);
};

/** Applies in/out transitions (whip, zoom, glitch, fade) to a scene. */
export const TransitionWrap: React.FC<{
	duration: number;
	tin?: Transition;
	tout?: Transition;
	children: React.ReactNode;
}> = ({duration, tin, tout, children}) => {
	const f = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const S = unit(width, height);
	let tx = 0;
	let scale = 1;
	let blurX = 0;
	let blurY = 0;
	let rgb = 0;
	let opacity = 1;
	const r = duration - f;

	if (tin === 'whip') {
		const k = 1 - easeOut(clamp(f / 7, 0, 1));
		tx += k * width * 0.7;
		blurX += k * 70 * S;
	} else if (tin === 'zoom') {
		const k = 1 - easeOut(clamp(f / 8, 0, 1));
		scale *= 1 + 0.6 * k;
		blurX += k * 22 * S;
		blurY += k * 22 * S;
	} else if (tin === 'glitch' && f < 6) {
		rgb += (6 - f) * 5 * S;
		tx += (random(`gj${f}`) - 0.5) * 60 * S;
	} else if (tin === 'fade') {
		opacity *= clamp(f / 10, 0, 1);
	} else if (tin === 'xfade') {
		opacity *= clamp(f / 15, 0, 1);
	} else if (tin === 'flash' || tin === 'impact') {
		scale *= 1 + 0.1 * (1 - easeOut(clamp(f / 10, 0, 1)));
	}

	if (tout === 'whip') {
		const k = easeIn(clamp(1 - r / 6, 0, 1));
		tx -= k * width * 0.7;
		blurX += k * 70 * S;
	} else if (tout === 'zoom') {
		const k = easeIn(clamp(1 - r / 5, 0, 1));
		scale *= 1 + 0.45 * k;
		blurX += k * 18 * S;
		blurY += k * 18 * S;
	} else if (tout === 'glitch' && r <= 3) {
		rgb += 12 * S;
		tx += (random(`go${f}`) - 0.5) * 50 * S;
	} else if (tout === 'fade') {
		opacity *= clamp(r / 8, 0, 1);
	}

	return (
		<AbsoluteFill style={{opacity}}>
			<Distort blurX={blurX} blurY={blurY} rgb={rgb} style={{transform: `translateX(${tx}px) scale(${scale})`}}>
				{children}
			</Distort>
		</AbsoluteFill>
	);
};

import {createContext, useContext} from 'react';
import {Easing, random} from 'remotion';
import type {ImageInfo, Manifest} from './types';

export const ManifestContext = createContext<Manifest | null>(null);
export const useManifest = (): Manifest => {
	const m = useContext(ManifestContext);
	if (!m) throw new Error('No manifest');
	return m;
};

export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeIn = Easing.bezier(0.5, 0, 0.75, 0);

/** Size unit: 1 at 1080px on the short side. */
export const unit = (w: number, h: number) => Math.min(w, h) / 1080;

export type Framed = {s: number; left: number; top: number; dw: number; dh: number};

/**
 * Place an image in a W x H frame.
 *  - 'cover': fill the frame
 *  - 'car':   scale so the whole vehicle is visible (bands are filled with a blurred copy)
 * focus is a point in normalized image coords that is centered when possible.
 */
export function frameImage(
	img: ImageInfo,
	W: number,
	H: number,
	mode: 'cover' | 'car',
	zoom = 1,
	focus?: [number, number],
): Framed {
	const cover = Math.max(W / img.w, H / img.h);
	const fit = Math.min(W / img.w, H / img.h);
	const [x0, y0, x1, y1] = img.box;
	const bw = (x1 - x0) * img.w;
	const bh = (y1 - y0) * img.h;
	const carS = Math.min((0.94 * W) / bw, (0.8 * H) / bh);
	const base = mode === 'cover' ? cover : clamp(carS, fit, cover);
	const s = base * zoom;
	const [fx, fy] = focus ?? [(x0 + x1) / 2, (y0 + y1) / 2];
	const dw = img.w * s;
	const dh = img.h * s;
	let left = W / 2 - fx * dw;
	let top = H / 2 - fy * dh;
	left = dw >= W ? clamp(left, W - dw, 0) : clamp(left, 0, W - dw);
	top = dh >= H ? clamp(top, H - dh, 0) : clamp(top, 0, H - dh);
	return {s, left, top, dw, dh};
}

/** Deterministic smooth-ish noise in [-1, 1]. */
export const noise1 = (seed: string | number, t: number) => {
	const i = Math.floor(t);
	const f = t - i;
	const a = random(`${seed}-${i}`) * 2 - 1;
	const b = random(`${seed}-${i + 1}`) * 2 - 1;
	const u = f * f * (3 - 2 * f);
	return a + (b - a) * u;
};

/** Split a title into at most two balanced lines. */
export function splitTitle(title: string): string[] {
	const words = title.trim().split(/\s+/).filter(Boolean);
	if (words.length <= 1 || title.length <= 14) return [title.trim()];
	let best = 1;
	let bestDiff = Infinity;
	for (let i = 1; i < words.length; i++) {
		const d = Math.abs(words.slice(0, i).join(' ').length - words.slice(i).join(' ').length);
		if (d < bestDiff) {
			bestDiff = d;
			best = i;
		}
	}
	return [words.slice(0, best).join(' '), words.slice(best).join(' ')];
}

/** Font size that fits `chars` characters of a condensed display font in `width`. */
const WIDE = /[　-ヿ㐀-鿿豈-﫿＀-￯]/;

/** Length of a string in "average glyph" units: full-width CJK characters are ~1em wide, i.e. 1/ratio glyphs. */
export const visLen = (s: string, ratio = 0.5) => {
	let n = 0;
	for (const ch of s) n += WIDE.test(ch) ? 1 / ratio : 1;
	return n;
};

export const fitFont = (chars: number, width: number, ratio = 0.5, max = 9999) =>
	Math.min(max, width / Math.max(1, chars * ratio));

export const hexA = (hex: string, a: number) => {
	const h = hex.replace('#', '');
	const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
	return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

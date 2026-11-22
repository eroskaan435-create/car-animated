import {loadFont as anton} from '@remotion/google-fonts/Anton';
import {loadFont as bebas} from '@remotion/google-fonts/BebasNeue';
import {loadFont as cinzel} from '@remotion/google-fonts/Cinzel';
import {loadFont as montserrat} from '@remotion/google-fonts/Montserrat';
import {loadFont as orbitron} from '@remotion/google-fonts/Orbitron';
import {loadFont as oswald} from '@remotion/google-fonts/Oswald';
import {loadFont as rajdhani} from '@remotion/google-fonts/Rajdhani';
import {loadFont as teko} from '@remotion/google-fonts/Teko';

const opts = {subsets: ['latin'] as any[]};
const LOADERS: Record<string, () => {fontFamily: string}> = {
	Anton: () => anton('normal', opts),
	BebasNeue: () => bebas('normal', opts),
	Cinzel: () => cinzel('normal', {...opts, weights: ['600', '800']} as any),
	Montserrat: () => montserrat('normal', {...opts, weights: ['500', '700', '800']} as any),
	Orbitron: () => orbitron('normal', {...opts, weights: ['700', '900']} as any),
	Oswald: () => oswald('normal', {...opts, weights: ['500', '700']} as any),
	Rajdhani: () => rajdhani('normal', {...opts, weights: ['600', '700']} as any),
	Teko: () => teko('normal', {...opts, weights: ['500', '600']} as any),
};

const cache: Record<string, string> = {};

/** Load a font by preset name and return its CSS family. */
export function font(name: string): string {
	if (cache[name]) return cache[name];
	const loader = LOADERS[name] ?? LOADERS.Anton;
	cache[name] = `"${loader().fontFamily}", Impact, "Noto Sans CJK JP", "Noto Sans JP", sans-serif`;
	return cache[name];
}

/** Approximate average glyph width (in em) of uppercase text, for fitting titles. */
const RATIO: Record<string, number> = {
	Anton: 0.47, BebasNeue: 0.42, Oswald: 0.52, Teko: 0.44, Orbitron: 0.86, Cinzel: 0.78, Rajdhani: 0.55, Montserrat: 0.74,
};
export const fontRatio = (name: string) => RATIO[name] ?? 0.55;

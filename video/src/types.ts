export type Spec = {label: string; value: string};

export type ImageInfo = {
	src: string;
	bg: string;
	cutout: string | null;
	depth: string | null;
	w: number;
	h: number;
	box: [number, number, number, number];
	carDepth: number;
	caption: string;
	category?: string;
};

export type Move = 'punch' | 'panLR' | 'panRL' | 'pushIn' | 'pullOut' | 'depth' | 'slide';
export type Transition = 'whip' | 'flash' | 'glitch' | 'zoom' | 'fade' | 'impact' | 'cut' | 'xfade';

export type Scene = {
	type: 'intro' | 'hero' | 'shot' | 'specs' | 'price' | 'outro' | 'chapter' | 'proscons' | 'endscreen';
	calm?: boolean;
	from: number;
	duration: number;
	image?: number;
	move?: Move;
	transitionIn?: Transition;
	transitionOut?: Transition;
	cues?: Record<string, any>;
};

export type TimelineEvent = {type: 'impact' | 'whoosh' | 'pop' | 'riser'; frame: number; strength?: number; duration?: number};

export type Theme = {
	name: string;
	accent: string;
	accent2: string;
	bg: string;
	fontDisplay: string;
	fontBody: string;
	fx: {
		shake: number;
		glitch: boolean;
		speedLines: boolean;
		particles: 'sparks' | 'dust' | 'bokeh' | 'neon' | 'none';
		lightSweep: boolean;
		flash: number;
		grain: number;
		beatPulse: number;
		floor: 'grid' | 'spot';
	};
};

export type Car = {
	title: string;
	tagline: string;
	price: string;
	priceLabel: string;
	specs: Spec[];
	dealer: string;
	contact: string;
	cta: string;
	logo: string | null;
};

export type Manifest = {
	fps: number;
	width: number;
	height: number;
	format: string;
	durationInFrames: number;
	beatFrames: number;
	finalHit: number;
	theme: Theme;
	car: Car;
	images: ImageInfo[];
	scenes: Scene[];
	events: TimelineEvent[];
	audio: string | null;
	grain: string | null;
	mode?: 'short' | 'long';
	captions?: {from: number; to: number; text: string}[];
	burnCaptions?: boolean;
	callouts?: {from: number; to: number; label: string; value: string}[];
	chapters?: {index: number; title: string; from: number; to: number; hidden?: boolean}[];
	pulseUntil?: number;
	thumbnail?: {text: string; badge: string};
};

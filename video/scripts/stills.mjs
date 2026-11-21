// Render preview stills: node scripts/stills.mjs public/job/props-9x16.json out/stills 0.5 100 200 ...
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';

const [propsFile, outDir = 'out/stills', scale = '0.5', ...frames] = process.argv.slice(2);
const inputProps = JSON.parse(fs.readFileSync(propsFile, 'utf8'));
fs.mkdirSync(outDir, {recursive: true});
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id: process.env.COMP || 'CarAd', inputProps});
const list = frames.length ? frames.map(Number) : inputProps.scenes.map((s) => s.from + Math.floor(s.duration / 2));
for (const frame of list) {
	const output = path.join(outDir, `f${String(frame).padStart(4, '0')}.jpg`);
	await renderStill({composition, serveUrl, inputProps, frame, output, imageFormat: 'jpeg', scale: Number(scale), chromiumOptions: {gl: process.env.GL || 'angle'}});
	console.log('wrote', output);
}

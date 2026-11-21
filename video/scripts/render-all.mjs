// Render the formats listed in public/job/renders.json (written by pipeline/prep.py).
//   node scripts/render-all.mjs <outDir>
// Env:
//   GL=swangle|angle (default swangle for CI), CONCURRENCY (default 4), SCALE (default 1)
//   CHUNK=i CHUNKS=n   long video: render only frame-slice i of n, video-only (joined + muxed later)
//   THUMB_ONLY=1       long video: only render the YouTube thumbnail
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';

const outDir = path.resolve(process.argv[2] || 'out');
const jobDir = path.resolve('public/job');
const renders = JSON.parse(fs.readFileSync(path.join(jobDir, 'renders.json'), 'utf8'));
const gl = process.env.GL || 'swangle';
const concurrency = Number(process.env.CONCURRENCY || 4);
const scale = Number(process.env.SCALE || 1);
const chunks = process.env.CHUNKS ? Number(process.env.CHUNKS) : 0;
const chunk = Number(process.env.CHUNK || 0);
const thumbOnly = process.env.THUMB_ONLY === '1';
fs.mkdirSync(outDir, {recursive: true});

console.log('Bundling...');
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});

const progress = (label, t0) => {
	let last = -1;
	return ({progress: p}) => {
		const pct = Math.floor(p * 20) * 5;
		if (pct !== last) {
			last = pct;
			console.log(`  ${label}: ${pct}%  (${Math.round((Date.now() - t0) / 1000)}s)`);
		}
	};
};

for (const r of renders) {
	const inputProps = JSON.parse(fs.readFileSync(path.join(jobDir, r.props), 'utf8'));
	const t0 = Date.now();

	if (r.long) {
		if (thumbOnly) {
			const thumb = await selectComposition({serveUrl, id: 'Thumbnail', inputProps, chromiumOptions: {gl}});
			await renderStill({composition: thumb, serveUrl, inputProps, frame: 0, output: path.join(outDir, r.poster), imageFormat: 'jpeg', jpegQuality: 95, chromiumOptions: {gl}});
			console.log('thumbnail ->', r.poster);
			continue;
		}
		const composition = await selectComposition({serveUrl, id: 'CarAd', inputProps, chromiumOptions: {gl}});
		const total = composition.durationInFrames;
		let frameRange = null;
		let output = path.join(outDir, r.output);
		if (chunks > 0) {
			const size = Math.ceil(total / chunks);
			const a = chunk * size;
			const b = Math.min(total - 1, a + size - 1);
			if (a > b) {
				console.log('nothing to render in this chunk');
				continue;
			}
			frameRange = [a, b];
			output = path.join(outDir, `chunk-${String(chunk).padStart(3, '0')}.mp4`);
		}
		console.log(`Rendering long video ${frameRange ? `frames ${frameRange[0]}-${frameRange[1]}` : `(${total} frames)`} -> ${output}`);
		await renderMedia({
			composition,
			serveUrl,
			inputProps,
			codec: 'h264',
			crf: 20,
			x264Preset: 'medium',
			imageFormat: 'jpeg',
			jpegQuality: 90,
			pixelFormat: 'yuv420p',
			scale,
			concurrency,
			frameRange,
			muted: chunks > 0,
			audioBitrate: '256k',
			outputLocation: output,
			chromiumOptions: {gl},
			timeoutInMilliseconds: 120000,
			onProgress: progress('long', t0),
		});
		console.log(`Done in ${Math.round((Date.now() - t0) / 1000)}s`);
		continue;
	}

	const composition = await selectComposition({serveUrl, id: 'CarAd', inputProps, chromiumOptions: {gl}});
	const output = path.join(outDir, r.output);
	console.log(`Rendering ${r.format} -> ${output} (${composition.durationInFrames} frames)`);
	await renderMedia({
		composition,
		serveUrl,
		inputProps,
		codec: 'h264',
		crf: 18,
		audioBitrate: '320k',
		imageFormat: 'jpeg',
		jpegQuality: 92,
		pixelFormat: 'yuv420p',
		scale,
		concurrency,
		outputLocation: output,
		chromiumOptions: {gl},
		timeoutInMilliseconds: 120000,
		onProgress: progress(r.format, t0),
	});
	await renderStill({
		composition,
		serveUrl,
		inputProps,
		frame: Math.min(r.posterFrame, composition.durationInFrames - 1),
		output: path.join(outDir, r.poster),
		imageFormat: 'jpeg',
		scale,
		chromiumOptions: {gl},
	});
	console.log(`Done ${r.format} in ${Math.round((Date.now() - t0) / 1000)}s`);
}

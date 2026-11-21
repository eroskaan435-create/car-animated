import React from 'react';
import {CalculateMetadataFunction, Composition, staticFile} from 'remotion';
import {CarAd} from './CarAd';
import {Thumbnail} from './Thumbnail';
import type {Manifest} from './types';

const empty = {images: [], scenes: []} as unknown as Manifest;

// When rendered with --props the manifest is passed in. In the Studio (no props)
// we load the last prepared job from public/job.
const calculateMetadata: CalculateMetadataFunction<Manifest> = async ({props}) => {
	let m = props;
	if (!m.scenes || m.scenes.length === 0) {
		for (const f of ['job/props-long.json', 'job/props-9x16.json', 'job/props-16x9.json']) {
			const res = await fetch(staticFile(f));
			if (res.ok) {
				m = (await res.json()) as Manifest;
				break;
			}
		}
	}
	return {props: m, durationInFrames: m.durationInFrames, width: m.width, height: m.height, fps: m.fps};
};

const thumbMetadata: CalculateMetadataFunction<Manifest> = async (args) => {
	const r = await calculateMetadata(args);
	return {props: r.props, durationInFrames: 1, width: 1280, height: 720, fps: 30};
};

export const RemotionRoot: React.FC = () => (
	<>
	<Composition
		id="CarAd"
		component={CarAd}
		defaultProps={empty}
		calculateMetadata={calculateMetadata}
		width={1080}
		height={1920}
		fps={30}
		durationInFrames={300}
	/>
	<Composition
		id="Thumbnail"
		component={Thumbnail}
		defaultProps={empty}
		calculateMetadata={thumbMetadata}
		width={1280}
		height={720}
		fps={30}
		durationInFrames={1}
	/>
	</>
);

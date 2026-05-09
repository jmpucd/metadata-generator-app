import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html',
			precompress: false,
		}),
		// SvelteKit's prerenderer won't know about dynamic routes; disable prerendering
		// and let FastAPI's StaticFiles html=True handle SPA fallback.
		prerender: { entries: [] },
	}
};

export default config;

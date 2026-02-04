import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			// Proxy API requests to FastAPI backend
			'/classify': 'http://localhost:8000',
			'/session': 'http://localhost:8000',
			'/user': 'http://localhost:8000',
			'/upload-pdf': 'http://localhost:8000',
			'/upload-pdf-status': 'http://localhost:8000',
			'/migrate-guest-sessions': 'http://localhost:8000',
			'/debug': 'http://localhost:8000'
		}
	}
});

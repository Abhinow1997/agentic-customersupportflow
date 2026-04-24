import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  ssr: {
    noExternal: []
  },
  build: {
    rollupOptions: {
      external: ['snowflake-sdk']
    }
  }
});

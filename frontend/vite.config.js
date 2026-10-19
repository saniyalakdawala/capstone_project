import { defineConfig } from 'vite';

// Read the shared project .env file from the repository root.
// Vite only exposes variables with the VITE_ prefix to browser code.
export default defineConfig({
  envDir: '..',
});

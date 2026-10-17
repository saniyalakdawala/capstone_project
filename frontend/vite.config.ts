import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../', '')
  const gKey = env.VITE_GOOGLE_MAPS_API_KEY || env.GOOGLE_MAPS_API_KEY || ''
  return {
    plugins: [react(), tailwindcss()],
    envDir: '../',
    define: {
      '__GOOGLE_MAPS_KEY__': JSON.stringify(gKey)
    }
  }
})

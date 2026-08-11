import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// `base` solo importa para el build de producción (GitHub Pages, proyecto — no user site — se
// sirve bajo /<repo>/, no en la raíz del dominio). El workflow de deploy setea VITE_BASE_PATH;
// en dev y en cualquier otro build queda "/" (comportamiento de siempre).
export default defineConfig({
  base: process.env.VITE_BASE_PATH ?? '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})

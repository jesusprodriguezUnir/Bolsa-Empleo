import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  output: 'static',
  integrations: [tailwind()],
  // Permite importar positions.json desde fuera del directorio web/
  vite: {
    server: {
      fs: { allow: ['..'] },
    },
  },
});

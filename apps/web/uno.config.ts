import { defineConfig, presetWind4 } from 'unocss'

export default defineConfig({
  presets: [presetWind4()],
  theme: {
    colors: {
      ink: '#07060a',
      panel: '#14111a',
      line: '#2c2638',
      paper: '#f6f3fb',
      mute: '#a99bb8',
      glow: '#d946ef',
    },
    fontFamily: {
      sans: '"Avenir Next", "Segoe UI", sans-serif',
    },
  },
  shortcuts: {
    shell: 'mx-auto w-full max-w-6xl px-5',
    btn: 'inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold',
    'btn-primary': 'btn bg-glow text-ink hover:bg-#e879f9',
    'btn-ghost': 'btn border border-line text-paper hover:border-glow',
    card: 'rounded-2xl border border-line bg-panel p-5',
    navlink: 'text-sm text-mute hover:text-paper',
  },
})

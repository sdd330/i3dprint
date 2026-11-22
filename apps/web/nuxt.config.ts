import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

function loadHomeMysqlEnv() {
  const file = join(homedir(), '.mysql_env')
  if (!existsSync(file)) return
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue
    const raw = trimmed.startsWith('export ') ? trimmed.slice(7) : trimmed
    const eq = raw.indexOf('=')
    const key = raw.slice(0, eq).trim()
    let value = raw.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    if (!process.env[key]) process.env[key] = value
  }
}

loadHomeMysqlEnv()

export default defineNuxtConfig({
  compatibilityDate: '2026-11-22',
  ssr: true,
  modules: ['@unocss/nuxt', '@pinia/nuxt', '@vite-pwa/nuxt'],
  css: ['~/assets/css/base.css'],
  app: {
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      title: 'Violet Z',
      meta: [
        { name: 'theme-color', content: '#07060a' },
        { name: 'description', content: 'Violet Z 三维打印' },
      ],
      link: [
        { rel: 'icon', href: '/logo.jpg', type: 'image/jpeg' },
        { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' },
      ],
    },
  },
  runtimeConfig: {
    mysqlHost: process.env.MYSQL_HOST || '',
    mysqlPort: process.env.MYSQL_PORT || '3306',
    mysqlUser: process.env.MYSQL_USER || process.env.MYSQL_ROOT || '',
    mysqlPassword: process.env.MYSQL_PASSWORD || '',
    mysqlDatabase: process.env.MYSQL_DATABASE || 'i3dprint',
  },
  typescript: {
    strict: true,
  },
  nitro: {
    prerender: {
      crawlLinks: false,
      routes: ['/offline'],
    },
  },
  pwa: {
    registerType: 'autoUpdate',
    manifest: {
      name: 'Violet Z',
      short_name: 'Violet Z',
      description: '三维打印',
      lang: 'zh-CN',
      theme_color: '#07060a',
      background_color: '#07060a',
      display: 'standalone',
      start_url: '/',
      icons: [
        { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
        { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
        { src: 'pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    },
    generateSW: {
      globPatterns: ['**/*.{js,css,html,png,svg,jpg,ico,woff2}'],
      navigateFallback: '/offline',
    },
    client: {
      installPrompt: true,
    },
    devOptions: {
      enabled: false,
    },
  },
})

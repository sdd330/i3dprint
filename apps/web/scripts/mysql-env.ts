import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

/** 读取 ~/.mysql_env 补进 process.env；已有的环境变量优先，不覆盖。 */
export function loadMysqlEnv(file = join(homedir(), '.mysql_env')) {
  if (!existsSync(file)) return
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue
    const raw = trimmed.startsWith('export ') ? trimmed.slice(7) : trimmed
    const eq = raw.indexOf('=')
    const key = raw.slice(0, eq).trim()
    let value = raw.slice(eq + 1).trim()
    if (
      value.length >= 2 &&
      ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'")))
    ) {
      value = value.slice(1, -1)
    }
    if (!process.env[key]) process.env[key] = value
  }
}

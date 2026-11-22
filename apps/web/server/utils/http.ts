import { createError, getRequestIP, isError, type H3Event } from 'h3'

export function clientIp(event: H3Event) {
  return getRequestIP(event) ?? ''
}

export function asHttpError(error: unknown): never {
  if (isError(error) && error.statusCode && error.statusCode < 500) throw error
  console.error(error)
  throw createError({ statusCode: 503, statusMessage: '数据库不可用' })
}

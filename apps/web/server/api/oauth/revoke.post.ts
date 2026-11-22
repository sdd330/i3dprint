import { readBody, setResponseStatus } from 'h3'
import { revokeTokens } from '../../utils/oauth'

export default defineEventHandler(async (event) => {
  const body = await readBody<{ token?: string }>(event)
  const token = String(body?.token ?? '')
  if (token) await revokeTokens(token, token)
  setResponseStatus(event, 200)
  return { revoked: true }
})

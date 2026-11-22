import { createError, readBody } from 'h3'
import { OAUTH_CLIENT, exchangeAuthorizationCode, rotateRefreshToken } from '../../utils/oauth'

export default defineEventHandler(async (event) => {
  const body = await readBody<{
    grant_type?: string
    code?: string
    redirect_uri?: string
    client_id?: string
    code_verifier?: string
    refresh_token?: string
  }>(event)
  if (body?.client_id && body.client_id !== OAUTH_CLIENT) {
    throw createError({ statusCode: 400, statusMessage: '客户端无效' })
  }
  if (body?.grant_type === 'authorization_code') {
    const tokens = await exchangeAuthorizationCode({
      code: String(body.code ?? ''),
      verifier: String(body.code_verifier ?? ''),
      redirectUri: String(body.redirect_uri ?? ''),
    })
    return {
      token_type: 'Bearer',
      access_token: tokens.accessToken,
      refresh_token: tokens.refreshToken,
      expires_in: tokens.expiresIn,
      scope: tokens.scope,
    }
  }
  if (body?.grant_type === 'refresh_token') {
    const tokens = await rotateRefreshToken(String(body.refresh_token ?? ''))
    if (!tokens) throw createError({ statusCode: 400, statusMessage: '刷新令牌无效' })
    return {
      token_type: 'Bearer',
      access_token: tokens.accessToken,
      refresh_token: tokens.refreshToken,
      expires_in: tokens.expiresIn,
      scope: tokens.scope,
    }
  }
  throw createError({ statusCode: 400, statusMessage: '不支持的授权类型' })
})

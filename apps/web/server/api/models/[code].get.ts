import { getRouterParam } from 'h3'
import { getModel } from '../../utils/catalog'
import { asHttpError } from '../../utils/http'
import { requireUser } from '../../utils/session'

export default defineEventHandler(async (event) => {
  try {
    await requireUser(event)
    return await getModel(getRouterParam(event, 'code') ?? '')
  } catch (error) {
    asHttpError(error)
  }
})

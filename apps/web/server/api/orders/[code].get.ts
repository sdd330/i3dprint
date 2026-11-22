import { getRouterParam } from 'h3'
import { isStaff } from '../../utils/oauth'
import { getOrder } from '../../utils/catalog'
import { asHttpError } from '../../utils/http'
import { requireUser } from '../../utils/session'

export default defineEventHandler(async (event) => {
  try {
    const user = await requireUser(event)
    return await getOrder(getRouterParam(event, 'code') ?? '', isStaff(user) ? undefined : user.id)
  } catch (error) {
    asHttpError(error)
  }
})

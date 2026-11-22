import { isStaff } from '../utils/oauth'
import { listOrders } from '../utils/catalog'
import { asHttpError } from '../utils/http'
import { requireUser } from '../utils/session'

export default defineEventHandler(async (event) => {
  try {
    const user = await requireUser(event)
    return await listOrders(isStaff(user) ? undefined : user.id)
  } catch (error) {
    asHttpError(error)
  }
})

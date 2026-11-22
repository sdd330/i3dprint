import { readBody } from 'h3'
import { createOrder } from '../utils/orders'
import { asHttpError } from '../utils/http'
import { requireUser } from '../utils/session'

export default defineEventHandler(async (event) => {
  try {
    const user = await requireUser(event)
    const body = await readBody<{
      campaignCode?: string
      name?: string
      materialNo?: string
      color?: string
      remark?: string
    }>(event)
    return await createOrder(event, user, body ?? {})
  } catch (error) {
    asHttpError(error)
  }
})

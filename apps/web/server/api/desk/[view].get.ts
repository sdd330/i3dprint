import { getRouterParam } from 'h3'
import { loadDesk } from '../../utils/desk'
import { asHttpError } from '../../utils/http'
import { requireStaff } from '../../utils/session'

export default defineEventHandler(async (event) => {
  try {
    await requireStaff(event)
    return await loadDesk(getRouterParam(event, 'view') ?? '')
  } catch (error) {
    asHttpError(error)
  }
})

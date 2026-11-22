import { listModels } from '../utils/catalog'
import { asHttpError } from '../utils/http'
import { requireUser } from '../utils/session'

export default defineEventHandler(async (event) => {
  try {
    await requireUser(event)
    return await listModels()
  } catch (error) {
    asHttpError(error)
  }
})

import { listCampaigns } from '../utils/catalog'
import { asHttpError } from '../utils/http'
import { requireUser } from '../utils/session'

export default defineEventHandler(async (event) => {
  try {
    await requireUser(event)
    return await listCampaigns()
  } catch (error) {
    asHttpError(error)
  }
})

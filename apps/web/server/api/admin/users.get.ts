import { listStaffUsers } from '../../utils/desk'
import { asHttpError } from '../../utils/http'
import { requireStaff } from '../../utils/session'

export default defineEventHandler(async (event) => {
  try {
    await requireStaff(event)
    return await listStaffUsers()
  } catch (error) {
    asHttpError(error)
  }
})

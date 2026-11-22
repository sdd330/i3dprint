import { listStaffRoles } from '../../utils/desk'
import { asHttpError } from '../../utils/http'
import { requireStaff } from '../../utils/session'

export default defineEventHandler(async (event) => {
  try {
    await requireStaff(event)
    return await listStaffRoles()
  } catch (error) {
    asHttpError(error)
  }
})

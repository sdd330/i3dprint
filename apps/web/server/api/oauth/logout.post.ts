import { sendRedirect } from 'h3'
import { logout } from '../../utils/session'

export default defineEventHandler(async (event) => {
  await logout(event)
  return sendRedirect(event, '/login', 303)
})

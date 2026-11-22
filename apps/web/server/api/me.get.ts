import { requireUser, toPublicUser } from '../utils/session'

export default defineEventHandler(async (event) => {
  return toPublicUser(await requireUser(event))
})
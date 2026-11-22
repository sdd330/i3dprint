import { readBody } from 'h3'
import { savePrintRequirement } from '../../../utils/orders'
import { asHttpError } from '../../../utils/http'
import { requireUser } from '../../../utils/session'

export default defineEventHandler(async (event) => {
  try {
    const user = await requireUser(event)
    const body = await readBody<{ materialNo?: string; color?: string; strength?: string; note?: string }>(event)
    return await savePrintRequirement(user, String(event.context.params?.code ?? ''), {
      materialNo: String(body?.materialNo ?? ''),
      color: String(body?.color ?? ''),
      strength: String(body?.strength ?? ''),
      note: String(body?.note ?? ''),
    })
  } catch (error) {
    asHttpError(error)
  }
})

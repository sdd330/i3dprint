import { createError } from 'h3'
import mysql from 'mysql2/promise'

let pool: mysql.Pool | undefined

export function getDb() {
  const config = useRuntimeConfig()
  if (!config.mysqlHost || !config.mysqlUser) {
    throw createError({ statusCode: 503, statusMessage: '数据库不可用' })
  }
  if (!pool) {
    pool = mysql.createPool({
      host: config.mysqlHost,
      port: Number(config.mysqlPort),
      user: config.mysqlUser,
      password: config.mysqlPassword,
      database: config.mysqlDatabase,
      charset: 'utf8mb4',
      waitForConnections: true,
      connectionLimit: 10,
      dateStrings: true,
    })
  }
  return pool
}

export async function queryRows<T extends mysql.RowDataPacket>(sql: string, params: unknown[] = []) {
  const db = getDb()
  const [rows] = await db.query<T[]>(sql, params)
  return rows
}

export async function withTx<T>(fn: (conn: mysql.PoolConnection) => Promise<T>) {
  const conn = await getDb().getConnection()
  try {
    await conn.beginTransaction()
    const value = await fn(conn)
    await conn.commit()
    return value
  } catch (error) {
    await conn.rollback()
    throw error
  } finally {
    conn.release()
  }
}

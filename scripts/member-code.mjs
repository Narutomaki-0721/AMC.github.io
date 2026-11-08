import { randomBytes, createHash } from 'node:crypto'
const code=randomBytes(32).toString('base64url')
console.log('成员访问码（只交给本人）',code)
console.log('写入 MEMBERS_JSON 的 SHA-256',createHash('sha256').update(code).digest('hex'))

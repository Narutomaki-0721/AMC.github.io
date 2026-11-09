export const MAX_SOURCES = 64
export const BATCH_SIZE = 8

function invalid(message) {
  throw Object.assign(new Error(message), { status: 422 })
}

export function planCollection(spec, request) {
  const links = request.match(/https:\/\/[^\s<>"，。；、）】]+/g) || []
  const urls = [...new Set(links.map(link => link.replace(/[),.;]+$/, '')))]
  if (urls.length > MAX_SOURCES) invalid('单项任务最多接受 64 个指定链接，请拆成两个请求。')
  if (urls.length) spec.urls = urls

  const years = request.match(/\b(20\d{2})\s*(?:年?\s*[-~～—–至到])\s*(20\d{2})/)
  const letters = request.match(/([A-F])\s*[-~～—–至到]\s*([A-F])\s*(?:题|道)/i)
  const batches = []
  if (spec.section === '历年赛题收集' && years && letters) {
    const start = Number(years[1]), end = Number(years[2])
    const alphabet = 'ABCDEF'
    const first = alphabet.indexOf(letters[1].toUpperCase()), last = alphabet.indexOf(letters[2].toUpperCase())
    const problems = alphabet.slice(first, last + 1)
    if (end < start || !problems) invalid('请按从早到晚的年份和从 A 到 F 的题号范围提交。')
    spec.count = (end - start + 1) * problems.length
    if (spec.count > MAX_SOURCES) invalid('任务超过 64 条，请按年份拆成多个任务。')
    for (let year = start; year <= end; year++) {
      batches.push({label: year + ' 年 ' + problems.split('').join('、') + ' 题', year, letters: problems,
        count: problems.length, query: year + ' MCM ICM official contest problem PDFs'})
    }
  } else {
    const totals = [...request.matchAll(/(\d+)\s*(?:份|条|篇|个来源)/g)]
    if (totals.length === 1) spec.count = Number(totals[0][1])
    if (!Number.isInteger(spec.count) || spec.count < 1 || spec.count > MAX_SOURCES)
      invalid('单项任务需收录 1–64 条来源；超出时请拆成多个任务。')
    for (let offset = 0; offset < spec.count; offset += BATCH_SIZE) {
      const count = Math.min(BATCH_SIZE, spec.count - offset)
      batches.push({label: '来源 ' + (offset + 1) + '–' + (offset + count), count, query: spec.query})
    }
  }
  spec.batches = batches
  return spec
}

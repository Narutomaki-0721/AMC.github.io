export function terms(text) {
  const words = text.toLowerCase().match(/[a-z0-9]+|[\p{Script=Han}]+/gu) || []
  return new Set(words.flatMap(w => /[\p{Script=Han}]/u.test(w) && w.length > 1
    ? Array.from({length:w.length-1}, (_,i)=>w.slice(i,i+2)) : [w]))
}

export function retrieve(rows, messages, page, base) {
  let current = ''
  try { current = decodeURIComponent(String(page || '').split(/[?#]/)[0]).replace(base,'').replace(/^\//,'') } catch {}
  const question = messages.at(-1).content
  const primary = terms(question)
  const prior = terms(messages.slice(-4,-1).map(m=>m.content).join(' '))
  const links = question.match(/https?:\/\/[^\s）。，<>]+/g) || []
  const ranked = rows.map((r,i) => {
    const title = terms(r.title+' '+r.heading), body = terms(r.body)
    let score = current && r.path.split('#')[0] === current ? 6 : 0
    for (const w of primary) score += (title.has(w)?4:0)+(body.has(w)?1:0)
    for (const w of prior) if(title.has(w)) score += 0.4
    if (links.some(url=>r.body.includes(url))) score += 100
    if (/20\d\d/.test(question) && r.title.includes(question.match(/20\d\d/)[0])) {
      const letter=question.match(/([a-f])\s*题/i)?.[1]
      if(letter && r.path.endsWith('#problem-'+letter.toLowerCase())) score+=60
    }
    return {r,i,score}
  }).filter(hit=>hit.score>0).sort((a,b)=>b.score-a.score||a.i-b.i)
  const range = question.match(/(20\d{2})\s*年?\s*[-~～—–至到]\s*(20\d{2})/)
  const letters = question.match(/([A-F])\s*[-~～—–至到]\s*([A-F])\s*题/i)
  const selected=ranked.slice(0,10).map(hit=>hit.r)
  if(range && letters){
    for(const row of rows){
      const id=row.path.match(/\/(20\d{2})\.html#problem-([a-f])$/)
      if(id && id[1]>=range[1] && id[1]<=range[2] && id[2]>=letters[1].toLowerCase() && id[2]<=letters[2].toLowerCase() && !selected.includes(row)) selected.push(row)
      if(selected.length>=70) break
    }
  }
  return selected
}

export async function loadKnowledge(env) {
  const response=await fetch(env.SITE_ORIGIN+env.SITE_BASE+'knowledge.json',{cf:{cacheTtl:60}})
  if(!response.ok) throw Object.assign(Error('知识库索引暂不可用，请稍后重试。'),{status:503})
  const rows=await response.json()
  if(!Array.isArray(rows)||!rows.length) throw Object.assign(Error('知识库索引暂不可用，请稍后重试。'),{status:503})
  return rows
}

export function references(hits, ids) {
  if(!Array.isArray(ids)) return []
  const refs=new Map()
  for(const id of ids) {
    if(!Number.isInteger(id)||id<1||id>hits.length) continue
    const r=hits[id-1]
    refs.set(r.path,{path:r.path,title:r.heading===r.title?r.title:r.title+' · '+r.heading})
  }
  return [...refs.values()]
}

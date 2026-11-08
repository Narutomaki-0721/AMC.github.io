import { defineConfig } from 'vitepress'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
const groups = [['schedule','赛程消息'], ['problems','历年赛题收集'], ['resources','参考资料文档'], ['practice','笔记与练习']]
function entries(folder) {
  return readdirSync(join('docs', folder), { withFileTypes: true }).sort((a,b)=>a.name.localeCompare(b.name)).flatMap(entry => {
    const path = folder + '/' + entry.name
    if (entry.isDirectory()) return [{text: entry.name, collapsed: true, items: entries(path)}]
    if (!entry.name.endsWith('.md')) return []
    const title = readFileSync(join('docs',path),'utf8').match(/^# (.+)$/m)?.[1] || entry.name
    return [{text:title,link:'/'+path.slice(0,-3)}]
  })
}
export default defineConfig({
  lang:'zh-CN', title:'建模手记', description:'MCM / ICM 团队备赛知识库',
  base:process.env.SITE_BASE || '/',
  themeConfig:{siteTitle:'建模手记',outlineTitle:'本页目录',search:{provider:'local'},
    nav:[{text:'知识目录',link:'/'},{text:'任务流',link:'/tasks'}],
    sidebar:groups.map(([folder,text])=>({text,collapsed:false,items:entries(folder)}))}
})

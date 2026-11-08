import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DatabaseSync } from 'node:sqlite'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import worker from '../worker/index.mjs'

// Execute the production SQL with SQLite; mirror only the D1 methods the Worker uses.
function database(){
 const sqlite=new DatabaseSync(':memory:')
 sqlite.exec(readFileSync(new URL('../worker/schema.sql',import.meta.url),'utf8'))
 function prepare(sql,args=[]){
 const stmt=sqlite.prepare(sql)
 return {bind:(...values)=>prepare(sql,values),first:()=>stmt.get(...args),
 all:()=>({results:stmt.all(...args)}),run:()=>({meta:stmt.run(...args)}),reader:!!stmt.columns().length}
 }
 return {prepare,batch(queries){sqlite.exec('BEGIN');try{const rows=queries.map(q=>q.reader?q.all():q.run());sqlite.exec('COMMIT');return rows}catch(e){sqlite.exec('ROLLBACK');throw e}}}
}
test('chat, authorization, approval races, failure, retry and publication',async t=>{
 const token='local-test-member-token',admin='local-test-approver-token',hash=s=>createHash('sha256').update(s).digest('hex')
 const env={DB:database(),SITE_ORIGIN:'https://team.example',SITE_BASE:'/AMC.github.io/',MODEL_URL:'https://model.example',
 MEMBERS_JSON:JSON.stringify({[hash(token)]:{name:'member'},[hash(admin)]:{name:'reviewer',approver:true}}),RUNNER_KEY:'runner-key'}
 let dispatchCount=0
 t.mock.method(globalThis,'fetch',async url=>{
 if(String(url).includes('api.github.com')){dispatchCount++;return new Response(null,{status:204})}
 return Response.json({choices:[{message:{content:JSON.stringify({reply:'好的',spec:{title:'优化资料',section:'参考资料文档',count:1,criteria:'包含实例',query:'integer optimization'}})}}]})
 })
 const pending=[]
 async function api(path,body,key=admin){const r=await worker.fetch(new Request('https://api.example'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+key},body:body?JSON.stringify(body):undefined}),env,{waitUntil:p=>pending.push(p)});return [r.status,await r.json()]}
 const id=crypto.randomUUID()
 const input={id,messages:[{role:'user',content:'请收录优化资料'}]}
 assert.equal((await api('/chat',input,token))[1].task,id)
 assert.equal((await api('/tasks/'+id+'/approve',{},token))[0],403)
 const approvals=await Promise.all([api('/tasks/'+id+'/approve',{}),api('/tasks/'+id+'/approve',{})])
 assert.deepEqual(approvals.map(x=>x[0]).sort(),[200,409]);await Promise.all(pending)
 assert.equal(dispatchCount,1)
 const event=(n,run,event,extras={})=>api('/runner',{id,n,run,event,...extras},env.RUNNER_KEY)
 assert.ok((await event(1,'r1','claim'))[1].spec)
 assert.equal((await event(1,'dup','claim'))[1].skip,true)
 await event(1,'r1','failure',{message:'来源不足'})
 assert.equal((await api('/tasks/'+id+'/retry',{}))[0],200)
 await Promise.all(pending)
 assert.equal((await event(1,'r1','failure'))[0],409)
 await event(2,'r2','claim')
 await event(2,'r2','success',{message:'已发布',path:'resources/'+id+'.html'})
 const task=(await api('/tasks'))[1].tasks[0]
 assert.equal(task.status,'success');assert.equal(task.attempts.length,2);assert.match(task.attempts[1].log,/来源不足/)
 const other=crypto.randomUUID()
 await api('/chat',{...input,id:other},token)
 assert.equal((await api('/tasks/'+other+'/reject',{}))[1].status,'rejected')
 assert.equal((await api('/tasks/'+other+'/approve',{}))[0],409)
 assert.equal((await api('/tasks',null,'invalid'))[0],401)
})

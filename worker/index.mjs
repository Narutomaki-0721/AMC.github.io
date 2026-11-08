const sections=['赛程消息','历年赛题收集','参考资料文档','笔记与练习']
const now=()=>new Date().toISOString()
function fail(status,message){throw Object.assign(Error(message),{status})}
export function validateSpec(s){
 if(!s||!sections.includes(s.section)||!Number.isInteger(s.count)||s.count<1||s.count>8)fail(422,'模型未生成有效的归档栏目或数量')
 for(const key of ['title','criteria','query'])if(typeof s[key]!=='string'||!s[key].trim()||s[key].length>1600)fail(422,'任务字段不完整')
 return Object.fromEntries(['title','section','count','criteria','query'].map(k=>[k,s[k]]))
}
async function member(req,env){
 const raw=(req.headers.get('Authorization')||'').match(/^Bearer (.{16,256})$/)?.[1]
 if(!raw)fail(401,'请先输入成员访问码')
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw))),x=>x.toString(16).padStart(2,'0')).join('')
 const person=JSON.parse(env.MEMBERS_JSON||'{}')[hash]
 if(!person)fail(403,'成员访问码无效')
 return person
}
async function chat(env,user,data){
 const {id,messages,page}=data
 if(!/^[0-9a-f-]{36}$/.test(id)||!Array.isArray(messages)||!messages.length||messages.length>12||
 messages.some(m=>!['assistant','user'].includes(m.role)||typeof m.content!=='string'||m.content.length>4000)||messages.at(-1).role!=='user')fail(400,'请求格式不正确')
 const existing=await env.DB.prepare('SELECT id,author FROM tasks WHERE id=?').bind(id).first()
 if(existing){if(existing.author!==user.name)fail(409,'编号已被使用');return {reply:'任务已进入待审批。',task:id}}
 const instruction='你是美赛备赛助手。输出 JSON，普通问答返回 {reply:string}。用户明确要求收录或更新知识库时，额外输出 spec:{title,section,count,criteria,query}。section 从 '+sections.join('、')+' 中选择，count 为1到8。criteria 完整保留用户要求。不要声称任务已经执行。'
 const response=await fetch(env.MODEL_URL,{method:'POST',headers:{Authorization:'Bearer '+env.MODEL_KEY,'Content-Type':'application/json'},body:JSON.stringify({model:env.MODEL_NAME,messages:[{role:'system',content:instruction},...messages.map(({role,content})=>({role,content}))],response_format:{type:'json_object'}}),signal:AbortSignal.timeout(60000)})
 if(!response.ok)fail(502,'模型服务暂时无法完成请求 ('+response.status+')')
 const result=JSON.parse((await response.json()).choices[0].message.content)
 if(typeof result.reply!=='string')fail(502,'模型回复无效')
 if(!result.spec)return {reply:result.reply}
 const spec=validateSpec(result.spec)
 const links=messages.at(-1).content.match(/https:\/\/[^\s<>"，。；、）】]+/g)||[]
 if(links.length)spec.urls=[...new Set(links.map(link=>link.replace(/[),.;]+$/,'')))].slice(0,8)
 await env.DB.prepare('INSERT INTO tasks(id,author,created,request,page,spec) VALUES(?,?,?,?,?,?)').bind(id,user.name,now(),messages.at(-1).content,String(page||'').slice(0,300),JSON.stringify(spec)).run()
 return {reply:'已生成待审批任务：'+spec.title+'\n'+spec.section+' · '+spec.count+' 条\n'+spec.criteria,task:id}
}
export async function decide(db,id,action,user){
 if(!user.approver)fail(403,'需要审批权限')
 const retry=action==='retry',reject=action==='reject'
 const status=reject?'rejected':'running'
 const q=retry?"UPDATE tasks SET status='running',attempt=attempt+1 WHERE id=? AND status='failed'":
 'UPDATE tasks SET status=?,reviewer=?,reviewed=?,attempt=attempt+? WHERE id=? AND status=\'pending\''
 const statement=db.prepare(q)
 const result=await (retry?statement.bind(id):statement.bind(status,user.name,now(),reject?0:1,id)).run()
 if(!result.meta.changes)fail(409,'任务已变化，请刷新')
 return {status}
}
async function pump(env){
 const time=Date.now()
 const {results}=await env.DB.prepare("SELECT a.* FROM attempts a JOIN tasks t ON t.id=a.task AND t.attempt=a.n WHERE t.status='running' AND a.touched<? LIMIT 30").bind(time-180000).all()
 for(const a of results){
 if(a.run){if(a.touched<time-3600000)await finish(env,a.task,a.n,a.run,false,'执行超时，未收到完成回报');continue}
 const reservation=await env.DB.prepare('UPDATE attempts SET touched=? WHERE task=? AND n=? AND touched=? AND run IS NULL').bind(time,a.task,a.n,a.touched).run()
 if(!reservation.meta.changes)continue
 const r=await fetch('https://api.github.com/repos/'+env.REPO+'/actions/workflows/collect.yml/dispatches',{method:'POST',headers:{Authorization:'Bearer '+env.DISPATCH_TOKEN,'User-Agent':'mcm-hub','Content-Type':'application/json'},body:JSON.stringify({ref:env.BRANCH||'main',inputs:{task:a.task,attempt:String(a.n)}})})
 if(!r.ok)await finish(env,a.task,a.n,null,false,'GitHub 派发失败，HTTP '+r.status)
 }
}
async function finish(env,id,n,run,success,message,url=null){
 const stage=success?'已发布':'失败'
 await env.DB.batch([
 env.DB.prepare('UPDATE tasks SET status=? WHERE id=? AND attempt=? AND status=\'running\' AND EXISTS(SELECT 1 FROM attempts WHERE task=? AND n=? AND run IS ?)')
 .bind(success?'success':'failed',id,n,id,n,run),
 env.DB.prepare('UPDATE attempts SET stage=?,log=log||?,url=?,touched=? WHERE task=? AND n=? AND run IS ? AND stage NOT IN (\'失败\',\'已发布\')').bind(stage,'\n'+now()+' '+message,url,Date.now(),id,n,run)])
}
async function runner(req,env){
 if(!env.RUNNER_KEY||req.headers.get('Authorization')!=='Bearer '+env.RUNNER_KEY)fail(403,'无执行权限')
 const {id,n,run,event,message,path}=await req.json()
 const db=env.DB
 if(event==='claim'){
 const reservation=await db.prepare("UPDATE attempts SET run=?,touched=?,stage='检索中' WHERE task=? AND n=? AND run IS NULL AND stage='排队中' AND EXISTS(SELECT 1 FROM tasks WHERE id=? AND attempt=? AND status='running')").bind(run,Date.now(),id,n,id,n).run()
 if(!reservation.meta.changes)return {skip:true}
 const t=await db.prepare('SELECT spec FROM tasks WHERE id=?').bind(id).first()
 return {spec:JSON.parse(t.spec)}
 }
 const a=await db.prepare('SELECT a.run FROM attempts a JOIN tasks t ON t.id=a.task WHERE a.task=? AND a.n=? AND t.attempt=a.n AND t.status=\'running\'').bind(id,n).first()
 if(!a||a.run!==run)fail(409,'该次执行已结束')
 const detail=String(message||'').slice(0,1200)
 if(event==='progress')await db.prepare('UPDATE attempts SET stage=?,log=log||?,touched=? WHERE task=? AND n=?').bind(detail,'\n'+now()+' '+detail,Date.now(),id,n).run()
 else if(event==='failure'||event==='success'){
 let url=null
 if(event==='success'){if(typeof path!=='string'||!new RegExp('^(schedule|resources|practice|problems)/'+id+'\\.html$').test(path))fail(400,'无效发布地址')
 url=env.SITE_ORIGIN+env.SITE_BASE+path}
 await finish(env,id,n,run,event==='success',detail,url)
 }else fail(400,'未知事件')
 return {ok:true}
}
async function route(req,env,ctx){
 const path=new URL(req.url).pathname
 if(path==='/runner'&&req.method==='POST')return runner(req,env)
 const user=await member(req,env)
 if(path==='/me')return {name:user.name,approver:!!user.approver}
 if(path==='/chat'&&req.method==='POST')return chat(env,user,await req.json())
 if(path==='/tasks'&&req.method==='GET'){
 const [{results:tasks},{results:attempts}]=await env.DB.batch([env.DB.prepare('SELECT * FROM tasks ORDER BY created DESC'),env.DB.prepare('SELECT * FROM attempts ORDER BY n DESC')])
 return {approver:!!user.approver,tasks:tasks.map(t=>({...t,spec:JSON.parse(t.spec),attempts:attempts.filter(a=>a.task===t.id)}))}
 }
 const match=path.match(/^\/tasks\/([a-f0-9-]{36})\/(approve|reject|retry)$/)
 if(match&&req.method==='POST'){const result=await decide(env.DB,match[1],match[2],user);if(result.status==='running')ctx.waitUntil(pump(env));return result}
 fail(404,'未找到接口')
}
export default {
 async fetch(req,env,ctx){
 const origin=req.headers.get('origin')
 if(origin&&origin!==env.SITE_ORIGIN)return new Response('Origin denied',{status:403})
 const headers={'Access-Control-Allow-Origin':env.SITE_ORIGIN,'Access-Control-Allow-Headers':'Authorization, Content-Type','Access-Control-Allow-Methods':'GET, POST, OPTIONS','Cache-Control':'no-store','Vary':'Origin'}
 if(req.method==='OPTIONS')return new Response(null,{status:204,headers})
 try{return Response.json(await route(req,env,ctx),{headers})}catch(e){return Response.json({error:e.status?e.message:'服务暂时不可用，请检查服务配置。'},{status:e.status||500,headers})}
 },
 async scheduled(_event,env){await pump(env)}
}

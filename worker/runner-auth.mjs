import {createRemoteJWKSet, jwtVerify} from 'jose'

const issuer = 'https://token.actions.githubusercontent.com'
const keys = createRemoteJWKSet(new URL(issuer+'/.well-known/jwks'))

export async function authorizeRunner(req, env, event, run, keySet=keys) {
  const token=(req.headers.get('Authorization') || '').replace(/^Bearer /,'')
  if(env.RUNNER_KEY && token===env.RUNNER_KEY) return
  try {
    const branch='refs/heads/'+(env.BRANCH||'main')
    const {payload}=await jwtVerify(token,keySet,{
      algorithms:['RS256'],issuer,audience:new URL(req.url).origin,
      requiredClaims:['exp','iat','repository','workflow_ref','ref','run_id','run_attempt','event_name']
    })
    if(!env.REPO_ID || payload.repository_id!==env.REPO_ID || payload.repository!==env.REPO || payload.ref!==branch ||
       payload.workflow_ref!==env.REPO+'/.github/workflows/collect.yml@'+branch ||
       !['schedule','workflow_dispatch','push'].includes(payload.event_name) ||
       run!==payload.run_id+'.'+payload.run_attempt ||
       (event!=='next' && payload.environment!=='github-pages')) throw Error()
  } catch {
    throw Object.assign(Error('无执行权限'),{status:403})
  }
}

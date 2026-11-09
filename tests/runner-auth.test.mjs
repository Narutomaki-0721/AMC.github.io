import test from 'node:test'
import assert from 'node:assert/strict'
import {generateKeyPair,SignJWT} from 'jose'
import {authorizeRunner} from '../worker/runner-auth.mjs'

test('runner binds signed credentials to the repository, workflow, audience, run and environment',async()=>{
 const {publicKey,privateKey}=await generateKeyPair('RS256')
 const env={REPO:'example/team',REPO_ID:'123'}
 const claims={repository:env.REPO,repository_id:'123',ref:'refs/heads/main',run_id:'72',run_attempt:'1',event_name:'schedule',
   workflow_ref:'example/team/.github/workflows/collect.yml@refs/heads/main'}
 async function verify(changes,event='next',run='72.1'){
   const token=await new SignJWT({...claims,...changes}).setProtectedHeader({alg:'RS256'})
     .setIssuer('https://token.actions.githubusercontent.com').setAudience('https://worker.test')
     .setIssuedAt().setExpirationTime('3m').sign(privateKey)
   return authorizeRunner(new Request('https://worker.test/runner',{headers:{Authorization:'Bearer '+token}}),env,event,run,publicKey)
 }
 await verify({})
 await verify({environment:'github-pages'},'claim')
 for(const changes of [{repository:'attacker/fork'},{repository_id:'999'},{ref:'refs/heads/topic'},{event_name:'pull_request'},{workflow_ref:'example/team/.github/workflows/other.yml@refs/heads/main'}]) await assert.rejects(verify(changes))
 await assert.rejects(verify({},'claim'))
 await assert.rejects(verify({},'next','73.1'))
})

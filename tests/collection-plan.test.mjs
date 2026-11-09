import {test} from 'node:test'
import assert from 'node:assert/strict'
import {planCollection} from '../worker/collection-plan.mjs'
const make = (count=8)=>({section:'历年赛题收集',query:'test',count})

test('explicit annual range overrides a model truncating the total to eight',()=>{
 const plan=planCollection(make(),'寻找2020-2026的A~E题')
 assert.equal(plan.count,35)
 assert.deepEqual(plan.batches.map(b=>b.year),[2020,2021,2022,2023,2024,2025,2026])
 assert.ok(plan.batches.every(b=>b.count===5&&b.letters==='ABCDE'))
})
test('generic totals, links and the boundary',()=>{
 const links=Array.from({length:12},(_,i)=>'https://example.edu/'+i)
 const plan=planCollection(make(8),'收录12份 '+links.join(' '))
 assert.deepEqual(plan.urls,links)
 assert.deepEqual(plan.batches.map(b=>b.count),[8,4])
 assert.throws(()=>planCollection(make(),'收录65条'),/64/)
})

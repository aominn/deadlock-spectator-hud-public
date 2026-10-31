import assert from 'node:assert/strict';
import {transientRequest,runLimits} from '../parser/live-receipt-producer.mjs';
let attempts=0,retries=0,waits=[];const options={pause:async ms=>waits.push(ms),onRetry:()=>retries++};
assert.equal(await transientRequest(async()=>{attempts++;if(attempts===1)throw new TypeError('network');if(attempts===2)throw Object.assign(new Error('HTTP'),{status:503});return 'ok';},options),'ok');assert.equal(attempts,3);assert.equal(retries,2);assert.deepEqual(waits,[500,1500]);
for(const error of [Object.assign(new Error('404'),{status:404}),new SyntaxError('JSON'),new Error('Byte bound reached'),new Error('Request bound reached')]){let count=0;await assert.rejects(transientRequest(async()=>{count++;throw error},options));assert.equal(count,1);}
let count=0;await assert.rejects(transientRequest(async()=>{count++;throw Object.assign(new Error('503'),{status:503})},options));assert.equal(count,3);
waits=[];attempts=0;await transientRequest(async()=>{if(!attempts++)throw Object.assign(new Error('429'),{status:429,retryAfterMs:5000});return true},options);assert.deepEqual(waits,[5000]);
count=0;await assert.rejects(transientRequest(async()=>{count++;throw new TypeError('network')},{...options,deadline:Date.now()}));assert.equal(count,1);
count=0;await assert.rejects(transientRequest(async()=>{count++;throw Object.assign(new Error('429'),{status:429,retryAfterMs:60000})},options));assert.equal(count,1,'long Retry-After is not ignored');
assert.deepEqual(runLimits(21600,{follow:true}),{follow:true,maxRequests:250,maxBytes:96*1024*1024,windowMs:180000});console.log('PASS transport retries:recover network+503;max3 attempts;404/schema/budgets stop;429 Retry-After respected;deadline;original request/byte limits');

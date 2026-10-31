import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../mod-src/spectator_probe.js',import.meta.url),'utf8');
let wall=0,jobs=[],reads=0,requests=0,output=[];
function panel(id,parent){return {id,style:{},visible:false,BHasClass:()=>false,GetParent:()=>parent,IsValid:()=>true,FindChildTraverse:()=>{reads++;return null;},FindChildrenWithClassTraverse:()=>{reads++;return [];},SetImage:()=>requests++};}
const root=panel('root',null),ctx=panel('top',root);const $={GetContextPanel:()=>ctx,Schedule:(delay,fn)=>jobs.push({at:wall+delay*1000,fn}),Msg:s=>output.push(s),CreatePanel:(_type,parent,id)=>panel(id,parent),RegisterEventHandler:()=>{}};
vm.runInNewContext(source,{$,Date:{now:()=>wall},Math,WeakMap});reads=0;requests=0;
while(jobs.length){jobs.sort((a,b)=>a.at-b.at);const job=jobs.shift();if(job.at>60000)break;wall=job.at;job.fn();}
assert.equal(reads,0,'normal match performs no clock,roster,modifier or geometry traversal');assert.equal(requests,0,'normal match makes no image/loopback requests');assert.equal(output.filter(x=>x.includes('[SpecSessionState]')).length,1);assert(!output.some(x=>/Error|ObserverHUD/.test(x)));
console.log('PASS full production probe60s normal match:no deep traversal or HTTP image requests;one mode transition log;timers stay available');

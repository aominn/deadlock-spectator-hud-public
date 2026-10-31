import {readFileSync} from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const full=readFileSync(new URL('../mod-src/spectator_probe.js',import.meta.url),'utf8'),code=full.slice(full.indexOf('// Native mode heartbeat:'),full.indexOf('// Session-local telestration display.'));
let wall=100000,classes=new Set(['connectedToHideout','connectedToHeroTesting']),jobs=[],out=[];
const root={BHasClass:x=>classes.has(x),GetParent:()=>null},ctx={BHasClass:()=>false,GetParent:()=>root,IsValid:()=>true};
vm.runInNewContext(code,{$:{GetContextPanel:()=>ctx,Schedule:(delay,fn)=>jobs.push({delay,fn}),Msg:s=>out.push(JSON.parse(s.split('[SpecSessionState] ')[1]))},Date:{now:()=>wall},Math});
function tick(ms){wall+=ms;const job=jobs.shift();assert.equal(job.delay,.5);job.fn()}
tick(0);assert.equal(out[0].flags.hideout,true);assert.equal(out[0].flags.practice,true);assert.equal(out[0].flags.spec,false);
for(let i=0;i<240;i++)tick(500);assert.equal(out.length,1,'idle lobby has no repetitive heartbeat');
classes=new Set();tick(500);assert.equal(out.length,2);assert.equal(out.at(-1).flags.hideout,false);
for(let i=0;i<240;i++)tick(500);assert.equal(out.length,2,'normal match has no repetitive heartbeat');
for(const flags of [['spec_mode','replay_playback','TeamSpectator'],['spec_mode','TeamSpectator'],['TeamSpectator']]){
 classes=new Set(flags);const start=out.length;tick(500);assert.equal(out.length,start+1,'mode transition is immediate');const first=out.at(-1).at;
 tick(500);tick(500);tick(500);assert.equal(out.length,start+1);tick(500);assert.equal(out.length,start+2);assert.equal(out.at(-1).at-first,2000,'active/paused spectator heartbeat remains every2s');
}
classes=new Set();tick(500);const end=out.length;assert.equal(out.at(-1).flags.teamSpectator,false);for(let i=0;i<120;i++)tick(500);assert.equal(out.length,end,'exit signal is emitted once,then quiet');
classes=new Set(['spec_mode','replay_playback']);tick(500);assert.equal(out.at(-1).flags.replay,true,'reentry is not lost after long idle');
assert.ok(out.every(x=>Object.keys(x).sort().join(',')==='at,flags,id,seq,v'));assert.ok(out.every((x,i)=>x.seq===i));
console.log('PASS native modes:500ms transition checks;normal/lobby quiet;live/replay/paused2s heartbeat;exit and reentry;no names or addresses');

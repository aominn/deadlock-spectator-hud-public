import assert from 'node:assert/strict';
import vm from 'node:vm';import {readFileSync} from 'node:fs';
const full=readFileSync(new URL('../mod-src/spectator_probe.js',import.meta.url),'utf8'),script=full.slice(full.indexOf('// Native money containers:'),full.indexOf('// Confirmed economy receipts:'));
let wall=10000,active=true,postgame=false;const scheduled=[],created=[],messages=[];
const root={BHasClass:c=>active&&(c==='spec_mode'||postgame&&c==='GameStatePostGame'),GetParent:()=>null};
const players=Array.from({length:12},(_,i)=>{const badge={heroid:i+1},name={text:'owner'+i},container={style:new Proxy({},{set:(target,key,value)=>{if(['width','height','flowChildren','opacity'].includes(key)&&value==='')throw new Error('empty native style');target[key]=value;return true;}}),classes:new Set(),AddClass(c){this.classes.add(c)},RemoveClass(c){this.classes.delete(c)}};
const player={paneltype:'CitadelHudTopBarPlayer',BHasClass:()=>false,GetParent:()=>root,FindChildTraverse:id=>id==='SoulsValue'?original:id==='HeroBadge'?badge:null,FindChildrenWithClassTraverse:()=>[name],badge,name};container.GetParent=()=>player;
const original={id:'SoulsValue',text:'14k',style:{},GetParent:()=>container};player.original=original;return player});
const clock={text:'0:54'},ctx={BHasClass:()=>false,GetParent:()=>root,FindChildTraverse:id=>id==='GameTime'?clock:null,FindChildrenWithClassTraverse:()=>[...players.map(p=>p.original),...created]};
const $={GetContextPanel:()=>ctx,Schedule:(_,fn)=>scheduled.push(fn),CreatePanel:(type,parent,id)=>{const n={id,type,style:{},classes:[],AddClass:c=>n.classes.push(c),GetParent:()=>parent,SetImage:url=>{n.url=url;n.requests=(n.requests||0)+1},handlers:{}};created.push(n);return n},RegisterEventHandler:(event,n,fn)=>n.handlers[event]=fn,Msg:m=>messages.push(m)};
const harness={SPEC_RESEARCH_LOGS:true,$,Date:{now:()=>wall},encodeURIComponent,JSON,String,Number};vm.runInNewContext(script,harness);
function tick(ms=100){wall+=ms;scheduled.shift()()}
function load(c){c.images[c.pending].handlers.ImageLoaded()}
function fail(c){c.images[c.pending].handlers.ImageFailedLoad()}
tick(0);const c=players[0]._specNativeMoney;assert.equal(created.length,36);assert.equal(c.fallback.text,'14k/—');assert.equal(c.state,'unknown');load(c);assert.equal(c.state,'fresh');assert.equal(c.original.text,'14k');assert.equal(c.original.style.visibility,'visible');assert.equal(c.original.style.opacity,'0');assert.equal(c.images[0].style.visibility,'visible');assert.ok(!('backgroundColor' in c.images[0].style));assert.equal(c.images[0].style.washColor,'#ffffff');
const requests=c.images.reduce((n,x)=>n+(x.requests||0),0);tick(400);assert.equal(c.images.reduce((n,x)=>n+(x.requests||0),0),requests,'no four requests per second');tick(100);assert.ok(c.pending>=0);players[0].original.text='14.1k';load(c);assert.equal(c.state,'held','native total changed during flight does not restore original');assert.equal(c.images[c.front].style.visibility,'visible');tick(250);fail(c);assert.equal(c.state,'held','temporary HTTP failure holds existing image');tick(1500);assert.equal(c.state,'unknown');assert.equal(c.fallback.text,'14.1k/—');assert.equal(c.front,-1);assert.equal(c.original.text,'14.1k');load(c);assert.equal(c.state,'fresh','recover from missing wallet');
// Scope invalidation cannot carry a former owner's wallet.
players[0].name.text='new owner';tick(100);assert.equal(c.state,'unknown');assert.equal(c.front,-1);load(c);assert.equal(c.state,'fresh');clock.text='0:10';tick(100);assert.equal(c.state,'unknown','rewind clears');load(c);clock.text='2:00';tick(100);assert.equal(c.state,'unknown','forward seek clears');load(c);
active=false;tick(100);assert.equal(c.state,'native');assert.equal(c.original.style.visibility,'visible');assert.ok(!c.container.classes.has('SpecNativeMoneyActive'));assert.equal(c.fallback.style.visibility,'collapse');
active=true;clock.text='2:01';tick(100);load(c);players[1].name.text='';tick(100);assert.equal(c.state,'native','ambiguous roster restores original');players[1].name.text='owner1';tick(100);assert.equal(c.state,'unknown');
const log=messages.filter(x=>x.startsWith('[SpecMoneyTransport] '));assert.ok(log.length);assert.ok(!log.join('').includes('owner'),'metrics do not record names');assert.match(full,/c&&c.state==='unknown'\?c.fallback:n/);console.log('PASS native transport:12 owners;500ms cadence;inflight total rejection holds;HTTP failure holds<=2s;unknown /—;recovery;owner/seek/exit clear;unchanged total;no personal data in counters');

harness.SPEC_RESEARCH_LOGS=false;const previousMetricsCount=messages.filter(x=>x.startsWith('[SpecMoneyTransport] ')).length;

// A stopped native game clock retains a confirmed wallet through long pauses.
load(c);const pausedFront=c.front;
for(let i=0;i<120;i++){tick(1000);if(c.pending>=0)fail(c);assert.equal(c.front,pausedFront);assert.equal(c.fallback.style.visibility,'collapse');}
assert.equal(c.state,'frozen');clock.text='2:02';tick(100);if(c.pending>=0)fail(c);assert.equal(c.state,'held','resume has a short recovery grace');assert.equal(c.front,pausedFront);
clock.text='2:03';tick(1000);if(c.pending>=0)fail(c);assert.equal(c.front,pausedFront);
clock.text='2:04';tick(1200);assert.equal(c.state,'unknown','running clock plus continued failure still expires honestly');
tick(1000);load(c);assert.equal(c.state,'fresh');tick(5000);if(c.pending>=0)fail(c);assert.equal(c.state,'frozen');players[0].original.text='15k';tick(100);assert.equal(c.state,'unknown','changed native total invalidates frozen image');
players[0].original.text='14.1k';tick(1000);load(c);tick(5000);if(c.pending>=0)fail(c);assert.equal(c.state,'frozen');players[0].name.text='third owner';tick(100);assert.equal(c.front,-1,'frozen money never carries to another owner');
console.log('PASS pause continuity:120seconds without image success retains confirmed money;resume2s grace;moving clock expires;recovery;native-total/owner invalidation');

load(c);postgame=true;const finalFront=c.front;clock.text='2:30';tick(1000);if(c.pending>=0)fail(c);assert.equal(c.front,finalFront,'confirmed postgame forward clock does not clear final money');
for(let i=0;i<60;i++){clock.text='3:'+String(i).padStart(2,'0');tick(1000);if(c.pending>=0)fail(c);assert.equal(c.front,finalFront);assert.equal(c.state,'ended');}
tick(500);clock.text='4:03';load(c);assert.equal(c.front,finalFront,'late postgame response cannot erase confirmed final money');assert.equal(c.state,'ended');
active=false;tick(100);assert.equal(c.front,-1);postgame=false;active=true;clock.text='0:01';tick(100);assert.equal(c.state,'unknown','new match never starts with previous final wallet');console.log('PASS final money:postgame class retains final confirmed image even while clock advances;exit andnewmatch clear');

active=true;clock.text='0:02';tick(100);assert.equal(c.container.style.width,'88px');assert.equal(c.container.style.height,'24px');for(const n of [c.fallback,...c.images]){assert.equal(n.style.ignoreParentFlow,true);assert.equal(n.style.horizontalAlign,'center');assert.equal(n.style.verticalAlign,'center');assert.equal(n.style.margin,'0px');assert.equal(n.style.padding,'0px');}active=false;tick(100);assert.equal(c.container.style.width,'fit-children');assert.equal(c.container.style.height,'fit-children');console.log('PASS initial fallback andloaded glyph share centered78px box inside88px native-sized container;exit restores dimensions');

assert.equal(c.fallback.style.width,'fit-children');assert.equal(c.fallback.style.maxWidth,'78px');assert.equal(c.fallback.style.height,'fit-children');console.log('PASS unknown text uses its actual width centered,not a left-painted full-width label');

assert.equal(c.original.style.opacity,'1');assert.equal(c.container.style.flowChildren,'right');console.log('PASS native text binding remains visible undertransparent glyph;exit restores flow andopacity');

for(const n of [c.fallback,...c.images])assert.equal(n.style.transform,'translateY(1px)');console.log('PASS user requested1px downward offset forboth loading andconfirmed money;original glyphbaseline retained');

assert.equal(messages.filter(x=>x.startsWith('[SpecMoneyTransport] ')).length,previousMetricsCount,'normal builds suppress research metrics without changing wallet updates');

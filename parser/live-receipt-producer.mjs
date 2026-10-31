import {attachBaseGuardians} from './base-guardian-parser.mjs';
import {attachEconomy} from './economy-parser.mjs';
import {attachMoney,attachSales,moneyClock} from './money-parser.mjs';
import {attachBridgeBuffs} from './bridge-buff-parser.mjs';
// Explicit bounded live producer. Reads only the TV route emitted by the native game.
// Local JSON contains a route digest, never the TV URL, Steam IDs or credentials.
import {readFileSync,writeFileSync,renameSync} from 'node:fs';
import {createHash,randomBytes} from 'node:crypto';
import {Readable} from 'node:stream';
import {pathToFileURL} from 'node:url';
import {Parser,ParserConfiguration,Logger,DemoSource,InterceptorStage,StringTableType,StringTableEvent,MessagePacketType,DemoPacketType} from 'deadem';
import {buildCatalog,pawnIdentity} from './extract-replay-effects.mjs';
import {LiveReceiptLedger} from './live-receipt-ledger.mjs';
export function nativeRoute(text){
 const rows=[...text.matchAll(/\[Client\].*creating client connection to '(https?:\/\/[^']+)'/g)];
 const raw=rows.at(-1)?.[1];if(!raw)throw Error('Native TV connection missing');
 const u=new URL(raw);
 if(!['http:','https:'].includes(u.protocol)||!u.hostname.endsWith('.steamcontent.com')||!/^\/tv\/[^/]+$/.test(u.pathname)||u.username||u.password||u.search||u.hash)throw Error('Native TV connection not supported');
 return raw;
}
export function attachLedger(parser,{session,routeSha,onSnapshot}){
 const demo=parser.getDemo(),ledger=new LiveReceiptLedger(buildCatalog());const bridge=attachBridgeBuffs(parser,{pawnIdentity,basis:'broadcast',maxUpdates:128});const money=attachMoney(parser,{basis:'broadcast',maxSamples:90}),sales=attachSales(parser,{basis:'broadcast'});const economy=attachEconomy(parser,{basis:'broadcast'});const baseGuardians=attachBaseGuardians(parser,{basis:'broadcast',maxUpdates:90});let entries=[],lastPublish=0,last=null,lastState=null;
 demo.stringTableContainer.subscribe(StringTableEvent.TABLE_CHANGED,(_,table,rows)=>{
  if(table.type===StringTableType.ACTIVE_MODIFIERS)for(const e of rows||[])if(e.value)entries.push({...e.value});
 });
 parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET,p=>{
  const roster=demo.getEntitiesByClassName('CCitadelPlayerPawn').map(pawnIdentity).filter(Boolean);
  const rules=demo.getEntitiesByClassName('CCitadelGameRulesProxy'),r=rules.length===1?rules[0]:null;
  const gameStart=r?.getField('m_pGameRules.m_flGameStartTime'),gameState=r?.getField('m_pGameRules.m_eGameState');
  const paused=r?.getField('m_pGameRules.m_bGamePaused'),pausedTicks=r?.getField('m_pGameRules.m_nTotalPausedTicks');
  // Native paused-clock fixture proves lastAppliedTime already excludes pause.
  // Normalize only the packet clock; active pauses establish a silent baseline.
  const streamSeconds=moneyClock(p.tick,r,'broadcast');
  const unsupportedPause=!Number.isInteger(pausedTicks)||pausedTicks<0||!Number.isFinite(streamSeconds);
  ledger.packet({tick:p.tick,roster,gameStart,gameState,paused:paused||unsupportedPause,pausedTicks,full:p.type===DemoPacketType.DEM_FULL_PACKET},entries);entries=[];
  const now=Date.now();last={schema:1,route_sha256:routeSha,session,generation:ledger.generation,updated_at:now/1000,
   state:unsupportedPause?'unsupported_paused_clock':ledger.state,game_seconds:streamSeconds,
   clock_basis:'server tick minus accumulated pause ticks, divided by64, minus native game start; application timestamps already exclude pause',game_state:gameState,paused_ticks:pausedTicks,
   roster,events:ledger.events,base_guardians:baseGuardians.snapshot(),bridge:bridge.snapshot(),money:{...money.snapshot(),sales:sales.snapshot()},economy:economy.snapshot(),metrics:ledger.metrics};
  if(now-lastPublish>=100||last.state!==lastState){onSnapshot(last);lastPublish=now;lastState=last.state;}
 });
 return {ledger,finish(state){if(last)onSnapshot({...last,updated_at:Date.now()/1000,state:last.game_state===11?'ended':state,events:[]});}};
}
export function atomicSnapshot(output,value,io={write:writeFileSync,rename:renameSync,pause:()=>Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,2)}){
 io.write(output+'.tmp',JSON.stringify(value));
 // Windows readers can briefly hold a non-delete-sharing file handle. Retry only
 // this local rename, at most20ms. Network requests are never retried here.
 for(let n=0;n<10;n++){
  try{io.rename(output+'.tmp',output);return;}
  catch(e){if(!['EPERM','EACCES','EBUSY'].includes(e.code)||n===9)throw e;io.pause();}
 }
}
export function runLimits(seconds,options={}){
 const follow=options.follow===true;
 if(!Number.isInteger(seconds)||seconds<5||seconds>(follow?21600:180))throw Error('Unsupported duration bound');
 if(options.expectedRoute!==undefined&&!/^[0-9a-f]{64}$/.test(options.expectedRoute))throw Error('Invalid expected route digest');
 return {follow,maxRequests:250,maxBytes:96*1024*1024,windowMs:180000};
}
// Retry only transient GET transport failures; parse/schema/budget/404 errors stop.
export async function transientRequest(operation,{deadline=Infinity,pause=ms=>new Promise(r=>setTimeout(r,ms)),onRetry=()=>{}}={}){
 for(let attempt=0;attempt<3;attempt++){
  try{return await operation();}catch(e){
   const retryable=[408,429,500,502,503,504].includes(e.status)||(!e.status&&(e.name==='TimeoutError'||e.name==='AbortError'||e instanceof TypeError));
   const delay=Math.max(attempt===0?500:1500,e.status===429?2000:0,Number(e.retryAfterMs)||0);
   if(!retryable||attempt===2||delay>10000||Date.now()+delay>=deadline)throw e;
   onRetry();await pause(delay);
  }
 }
}
export async function run(log,output,seconds=120,options={}){
 const limits=runLimits(seconds,options);
 const route=nativeRoute(readFileSync(log,'utf8')),routeSha=createHash('sha256').update(route).digest('hex'),session=randomBytes(16).toString('hex');
 if(options.expectedRoute&&options.expectedRoute!==routeSha)throw Error('Native route changed before producer startup');
 const atomic=x=>atomicSnapshot(output,x);
 const begin=Date.now(),deadline=begin+seconds*1000;let transientRetries=0,requests=0,bytes=0,windowStart=begin,windowRequests=0,windowBytes=0,firstSync=null,lastSync=null,error=null,success=false;
 const parser=new Parser(new ParserConfiguration({entityClasses:['CCitadelPlayerPawn','CCitadelPlayerController','CCitadelGameRulesProxy','CItemXP','CNPC_BarrackBoss'],messagePacketTypes:[MessagePacketType.SVC_PACKET_ENTITIES,MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,MessagePacketType.CITADEL_USER_MESSAGE_HERO_KILLED,MessagePacketType.CITADEL_USER_MESSAGE_BOSS_KILLED,MessagePacketType.CITADEL_USER_MESSAGE_ITEM_PURCHASE_NOTIFICATION]}),new Logger({debug(){},info(){},trace(){},warn(){},error(){}}));
 const adapter=attachLedger(parser,{session,routeSha,onSnapshot:atomic});
 async function singleRequest(suffix,json=false){
  if(limits.follow&&Date.now()-windowStart>=limits.windowMs){windowStart=Date.now();windowRequests=0;windowBytes=0;}
  if(Date.now()>deadline+10000||windowRequests>=limits.maxRequests)throw Error('Request bound reached');requests++;windowRequests++;
  const response=await fetch(route+'/'+suffix,{redirect:'error',signal:AbortSignal.timeout(10000)});
  if(!response.ok){const e=new Error('HTTP '+response.status);e.status=response.status;const retryAfter=response.headers.get('retry-after');if(retryAfter!==null){const v=Number(retryAfter);e.retryAfterMs=Number.isFinite(v)?Math.max(0,v*1000):Math.max(0,Date.parse(retryAfter)-Date.now());}try{await response.body?.cancel();}catch{}throw e;}
  const parts=[];let n=0;
  for await(const b of response.body){n+=b.length;bytes+=b.length;windowBytes+=b.length;if(n>16*1024*1024||windowBytes>limits.maxBytes)throw Error('Byte bound reached');parts.push(b);}
  const b=Buffer.concat(parts);return json?JSON.parse(b.toString('utf8')):b;
 }
 async function request(suffix,json=false){return transientRequest(()=>singleRequest(suffix,json),{deadline,onRetry:()=>{transientRetries++;}});}
 function sync(s){if(!Number.isInteger(s.fragment)||s.fragment<0||!Number.isInteger(s.signup_fragment)||s.signup_fragment<0||s.tps!==64)throw Error('Unsupported sync');return s;}
 async function* stream(){
  firstSync=lastSync=sync(await request('sync',true));let current=Math.max(1,lastSync.fragment-4);
  yield await request(lastSync.signup_fragment+'/start');yield await request(current+'/full');
  while(Date.now()<deadline&&adapter.ledger.state!=='ended'){
   if(current<=lastSync.fragment){yield await request(current+'/delta');current++;}
   else {await new Promise(r=>setTimeout(r,1000));if(Date.now()>=deadline)break;lastSync=sync(await request('sync',true));}
  }
 }
 try{await parser.parse(Readable.from(stream()),DemoSource.HTTP_BROADCAST);success=true;}
 catch(e){error={type:e.name,status:e.status||null,message:String(e.message).replace(/https?:\/\/\S+/g,'[URL]').slice(0,120)};}
 finally{adapter.finish(success?'stopped':'error');await parser.dispose();}
 const report={success,error,follow:limits.follow,session,route_sha256:routeSha,seconds:(Date.now()-begin)/1000,requests,bytes,transient_retries:transientRetries,first_sync:firstSync,last_sync:lastSync,final_state:adapter.ledger.state,metrics:adapter.ledger.metrics,events:adapter.ledger.events,
  scope:'bounded native TV read; no auto authentication; at most3 attempts per transient GET within existing budgets. HUD acceptance is separately gated by route, roster and native clock; current pause suppresses notifications; resume rebaselines; packet clock normalized by native pause ticks'};
 writeFileSync(output+'.report.json',JSON.stringify(report,null,2));const {events,...summary}=report;console.log(JSON.stringify({...summary,event_count:events.length}));return report;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const [log,output,seconds,...flags]=process.argv.slice(2);if(flags.some(x=>x!=='--follow'&&!/^[0-9a-f]{64}$/.test(x)))throw Error('Unsupported producer option');if(!log||!output)throw Error('Native log and local output paths required');
 try{const r=await run(log,output,seconds===undefined?120:Number(seconds),{follow:flags.includes('--follow'),expectedRoute:flags.find(x=>/^[0-9a-f]{64}$/.test(x))});if(!r.success)process.exitCode=1;}
 catch(e){console.log(JSON.stringify({success:false,error_type:e.name,message:String(e.message).replace(/https?:\/\/\S+/g,'[URL]').slice(0,120)}));process.exitCode=1;}
}

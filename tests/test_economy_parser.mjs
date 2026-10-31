import assert from 'node:assert/strict';
import {classifyEconomy,URN_ORB,attachEconomy} from '../parser/economy-parser.mjs';
import {InterceptorStage,MessagePacketType,DemoPacketType} from '../parser/node_modules/deadem/index.js';
const data={userid:3,currencyType:0,currencySource:33,delta:95,newValue:1000,entindexVictim:1234};const orb={active:true,class:{name:'CItemXP'},handle:1234,getField:()=>URN_ORB};
assert.equal(classifyEconomy(data,orb),'urn');assert.equal(classifyEconomy({...data,currencySource:23},orb),'urn-deny');assert.equal(classifyEconomy(data,{...orb,getField:()=>643818086}),null);assert.equal(classifyEconomy({...data,userid:-1},orb),null);assert.equal(classifyEconomy({...data,currencyType:3,currencySource:8,delta:-355},orb),null);assert.equal(classifyEconomy({...data,currencySource:0,delta:-800},orb),null);assert.equal(classifyEconomy({...data,currencySource:9,delta:-355},null),'loss');
function fixture(basis='replay'){
 const handlers=new Map(),pawns=Array.from({length:12},(_,i)=>({active:true,index:100+i,handle:100+i,class:{name:'CCitadelPlayerPawn'},getField:k=>k==='m_iTeamNum'?(i<6?2:3):undefined}));
 const cs=pawns.map((pawn,i)=>({active:true,index:i+1,getField:k=>({m_nHeroID:10+i,m_unLobbyPlayerSlot:i,m_iTeamNum:i<6?2:3,m_hHeroPawn:pawn.handle}[k])}));const rules={getField:k=>({'m_pGameRules.m_nTotalPausedTicks':0,'m_pGameRules.m_bGamePaused':false,'m_pGameRules.m_flGameStartTime':10,'m_pGameRules.m_eGameState':7}[k])};
 const demo={getEntitiesByClassName:n=>n==='CCitadelPlayerController'?cs:n==='CCitadelGameRulesProxy'?[rules]:pawns,getEntityByHandle:h=>pawns.find(p=>p.handle===h)||null};const parser={getDemo:()=>demo,registerPostInterceptor:(s,fn)=>{if(!handlers.has(s))handlers.set(s,[]);handlers.get(s).push(fn);}};const out=attachEconomy(parser,{basis});
 function emit(type,d,tick=10000){for(const f of handlers.get(InterceptorStage.MESSAGE_PACKET)||[])f({tick},{type,data:d});}
 function flush(tick=10000,type){for(const f of handlers.get(InterceptorStage.DEMO_PACKET)||[])f({tick,type});}
 return {emit,flush,out};
}
let f=fixture();const k={entindexVictim:106,entindexScorer:100,entindexAssisters:[101],victimTeamNumber:3};f.emit(MessagePacketType.CITADEL_USER_MESSAGE_HERO_KILLED,k);f.emit(MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,{...data,userid:0,currencySource:11,delta:500,entindexVictim:106});f.emit(MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,{...data,userid:6,currencySource:9,delta:-355,entindexVictim:undefined});f.emit(MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,{...data,userid:6,currencyType:3,currencySource:8,delta:-355});f.emit(MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,{...data,userid:-1,currencySource:38,delta:50});f.flush();assert.deepEqual(f.out.snapshot().events.map(e=>[e.hero,e.delta]),[[10,500],[16,-355]]);
// Reusing an entity across launches is not a dedupe key. Independent messages are retained.
f.emit(MessagePacketType.CITADEL_USER_MESSAGE_HERO_KILLED,k);f.emit(MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,{...data,userid:0,currencySource:11,delta:500,entindexVictim:106});f.flush(10001);assert.equal(f.out.snapshot().events.length,3);
// Wrong userid/controller convention disables the stream, not a guessed name match.
f=fixture();f.emit(MessagePacketType.CITADEL_USER_MESSAGE_HERO_KILLED,k);f.emit(MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,{...data,userid:1,currencySource:11,delta:500,entindexVictim:106});f.flush();assert.equal(f.out.snapshot().supported,false);
console.log('PASS:economy source/subtype/sign/unknown-ID exclusions,personal loss once,independent receipts,identity mismatch');

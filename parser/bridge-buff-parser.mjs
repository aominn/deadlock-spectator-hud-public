import {InterceptorStage,StringTableType,StringTableEvent,DemoPacketType} from 'deadem';
import {BridgeBuffLedger} from './bridge-buff-ledger.mjs';
// The caller supplies its existing exact pawn resolver; no extra connection.
export function attachBridgeBuffs(parser,{pawnIdentity,basis='replay',maxUpdates=20000}={}){
 const demo=parser.getDemo(),ledger=new BridgeBuffLedger(),updates=[];let table=null,changes=[],fingerprint=null,lastClock=-1,cachedPawns=[],lastRosterTick=-Infinity,lastSampleTick=-Infinity;
 demo.stringTableContainer.subscribe(StringTableEvent.TABLE_CHANGED,(_,t,rows)=>{if(t.type!==StringTableType.ACTIVE_MODIFIERS)return;table=t;for(const e of rows||[])if(ledger.slots.has(e.id)||ledger.rules.has(e.value?.modifierSubclass)||changes.some(x=>x.id===e.id))changes.push({id:e.id,value:e.value?{...e.value}:null});});
 parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET,p=>{
  // Sample idle ownership/death state at4Hz; modifier changes and full packets remain immediate.
  if(!changes.length&&p.type!==DemoPacketType.DEM_FULL_PACKET&&p.tick>=lastSampleTick&&p.tick-lastSampleTick<16)return;lastSampleTick=p.tick;
  const rules=demo.getEntitiesByClassName('CCitadelGameRulesProxy'),r=rules.length===1?rules[0]:null;
  const gameStart=r?.getField('m_pGameRules.m_flGameStartTime'),gameState=r?.getField('m_pGameRules.m_eGameState');
  const paused=r?.getField('m_pGameRules.m_bGamePaused'),total=r?.getField('m_pGameRules.m_nTotalPausedTicks'),pauseStart=r?.getField('m_pGameRules.m_nPauseStartTick');
  const supported=Number.isInteger(total)&&total>=0&&total<=p.tick;
  const pausedNow=paused&&Number.isInteger(pauseStart)&&pauseStart>0?Math.max(0,p.tick-pauseStart):0;
  const seconds=supported?(p.tick-total-pausedNow)/64-(basis==='broadcast'?gameStart:0):NaN;
  // Exact hero fields are checked every packet; enumerate the full pawn schema
  // only on a full packet or invalid identity.
  if(p.type===DemoPacketType.DEM_FULL_PACKET||p.tick<lastRosterTick||cachedPawns.length!==12||cachedPawns.some(x=>!x.pawn.active||x.pawn.getField(x.heroKey)!==x.owner.hero)){
   cachedPawns=demo.getEntitiesByClassName('CCitadelPlayerPawn').map(pawn=>{const owner=pawnIdentity(pawn);if(!owner)return null;const heroKey=[...pawn.fieldEntries()].find(([k,v])=>(k==='m_nHeroID'||k.endsWith('.m_nHeroID'))&&v===owner.hero)?.[0];return heroKey?{pawn,owner,heroKey}:null;}).filter(Boolean);lastRosterTick=p.tick;
  }
  const roster=cachedPawns.map(x=>({...x.owner,alive:x.pawn.getField('m_lifeState')===0}));
  const complete=()=>table?Array.from(table.getEntries()).map(e=>({id:e.id,value:e.value?{...e.value}:null})):[];
  const rows=ledger.packet({seconds,gameStart,roster,gameState,full:p.type===DemoPacketType.DEM_FULL_PACKET},changes,complete);changes=[];
  if(!Number.isFinite(seconds)||seconds<0)return;
  if(seconds<lastClock){ledger.reset();return;}
  const next=JSON.stringify([ledger.state,rows]);if(next!==fingerprint){updates.push({seconds,rows});fingerprint=next;if(updates.length>maxUpdates)updates.splice(0,updates.length-maxUpdates);}lastClock=seconds;
 });
 return {ledger,updates,snapshot(){return {schema:1,state:ledger.state,updates};}};
}

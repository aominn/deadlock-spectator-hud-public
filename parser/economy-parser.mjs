import {InterceptorStage,MessagePacketType,DemoPacketType} from 'deadem';
import {moneyClock} from './money-parser.mjs';
// Only proved EGold sources. Source33 also covers KOTH: the current orb subtype is mandatory.
export const URN_ORB=3283937835;
export function classifyEconomy(d,entity){
 if(d.currencyType!==0||!Number.isInteger(d.delta)||!d.delta||Math.abs(d.delta)>10000000||!Number.isInteger(d.userid)||d.userid<0||!Number.isInteger(d.newValue)||d.newValue<0)return null;
 const s=d.currencySource;
 if([11,12,38].includes(s)&&d.delta>0)return 'kill';
 if(s===13&&d.delta>0)return 'building';
 if(s===9&&d.delta<0)return 'loss';
 if([23,33].includes(s)&&d.delta>0&&entity?.active&&entity.class.name==='CItemXP'&&entity.handle===d.entindexVictim&&entity.getField('m_nSubclassID')===URN_ORB)return s===23?'urn-deny':'urn';
 return null;
}
export function attachEconomy(parser,{basis='replay',maxEvents=basis==='broadcast'?512:20000}={}){
 const demo=parser.getDemo(),events=[],metrics={accepted:0,unresolved:0,identity:0,unverified:0,baseline:0};let pending=[],kills=[],bosses=[],sequence=0,generation=0,previous=-1,mapping=false,conflict=false,overflow=false;
 function roster(){
  const cs=demo.getEntitiesByClassName('CCitadelPlayerController').filter(c=>c.active&&Number.isInteger(c.getField('m_nHeroID'))&&c.getField('m_nHeroID')>0&&[2,3].includes(c.getField('m_iTeamNum')));
  if(cs.some(c=>!Number.isInteger(c.getField('m_unLobbyPlayerSlot'))||c.getField('m_unLobbyPlayerSlot')<0||c.getField('m_unLobbyPlayerSlot')>23)||cs.length!==12||new Set(cs.map(c=>c.getField('m_nHeroID'))).size!==12||new Set(cs.map(c=>c.getField('m_unLobbyPlayerSlot'))).size!==12||cs.filter(c=>c.getField('m_iTeamNum')===2).length!==6)return [];
  return cs.map(c=>{const h=c.getField('m_hHeroPawn'),pawn=Number.isInteger(h)?demo.getEntityByHandle(h):null;return {c,pawn,hero:c.getField('m_nHeroID'),team:c.getField('m_iTeamNum')};}).filter(o=>o.pawn?.active&&o.pawn.class.name==='CCitadelPlayerPawn'&&o.pawn.getField('m_iTeamNum')===o.team);
 }
 parser.registerPostInterceptor(InterceptorStage.MESSAGE_PACKET,(p,m)=>{
  if(m.type===MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED){const d=m.data;pending.push({tick:p.tick,data:d,cause:classifyEconomy(d,demo.getEntityByHandle(d.entindexVictim??16777215))});}
  else if(m.type===MessagePacketType.CITADEL_USER_MESSAGE_HERO_KILLED)kills.push(m.data);
  else if(m.type===MessagePacketType.CITADEL_USER_MESSAGE_BOSS_KILLED)bosses.push(m.data);
 });
 parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET,p=>{
  const rules=demo.getEntitiesByClassName('CCitadelGameRulesProxy'),r=rules.length===1?rules[0]:null,t=moneyClock(p.tick,r,basis),owners=roster();
  const reset=basis==='broadcast'&&previous>=0&&(t<previous||p.type===DemoPacketType.DEM_FULL_PACKET);
  if(reset){events.length=0;generation++;mapping=false;conflict=false;}
  if(Number.isFinite(t))previous=t;
  const valid=Number.isFinite(t)&&t>=0&&[7,8].includes(r?.getField('m_pGameRules.m_eGameState'))&&owners.length===12&&!r?.getField('m_pGameRules.m_bGamePaused');
  function owner(d){return owners.find(o=>o.c.index===d.userid+1);}
  // Validate this stream's userid/controller-index convention against an actual kill scorer.
  // A mismatch disables receipts until a new stream/full baseline; never match by similar balances.
  for(const e of pending)if(e.cause==='kill'&&e.data.currencySource===11){const k=kills.find(k=>k.entindexVictim===(e.data.entindexVictim&16383)),o=owner(e.data);if(k&&o){if(k.entindexScorer===o.pawn.index)mapping=true;else conflict=true;}}
  if(valid&&mapping&&!conflict&&!reset){
   for(let i=0;i<pending.length;i++){
    const e=pending[i],d=e.data;if(!e.cause){if(d.currencyType===0&&[9,11,12,13,23,33,38].includes(d.currencySource))metrics.unresolved++;continue;}
    const o=owner(d);if(!o){metrics.identity++;continue;}
    let proved=true;
    if(['kill','loss'].includes(e.cause)){
     const k=kills.find(k=>k.entindexVictim===(e.cause==='loss'?o.pawn.index:(d.entindexVictim&16383)));
     proved=!!k&&(e.cause==='loss'?k.entindexVictim===o.pawn.index:d.currencySource===11?k.entindexScorer===o.pawn.index:d.currencySource===12?(k.entindexAssisters||[]).includes(o.pawn.index):k.victimTeamNumber!==o.team);
    }else if(e.cause==='building')proved=bosses.some(b=>b.entityKilled===d.entindexVictim&&[2,3].includes(b.objectiveTeam)&&b.objectiveTeam!==o.team);
    if(!proved){metrics.unverified++;continue;}
    if(events.length>=maxEvents&&basis!=='broadcast'){overflow=true;events.length=0;break;}
    events.push({id:generation+':'+e.tick+':'+i,sequence:++sequence,generation,tick:e.tick,seconds:t,hero:o.hero,team:o.team,parent:o.pawn.handle,cause:e.cause,delta:d.delta,new_value:d.newValue,source:d.currencySource,victim:d.entindexVictim});metrics.accepted++;
   }
   if(basis==='broadcast'&&events.length>maxEvents)events.splice(0,events.length-maxEvents);
  }else if(pending.length)metrics.baseline+=pending.length;
  pending=[];kills=[];bosses=[];
 });
 return {snapshot(){return {schema:1,supported:!overflow&&!conflict,generation,identity_verified:mapping&&!conflict,events:overflow?[]:events.slice(),metrics:{...metrics}};}};
}

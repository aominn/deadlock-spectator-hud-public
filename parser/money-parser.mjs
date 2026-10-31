import {InterceptorStage,MessagePacketType,DemoPacketType} from 'deadem';
// Controller values are authoritative. Do not derive wallet from item prices.
export function controllerMoney(demo){
 const rows=demo.getEntitiesByClassName('CCitadelPlayerController').filter(c=>c.active).map(c=>({hero:c.getField('m_nHeroID'),team:c.getField('m_iTeamNum'),total:c.getField('m_iGoldNetWorth'),wallet:c.getField('m_iGold'),slot:c.getField('m_unLobbyPlayerSlot')})).filter(c=>Number.isInteger(c.hero)&&c.hero>0&&[2,3].includes(c.team));
 if(rows.length!==12||new Set(rows.map(c=>c.hero)).size!==12||new Set(rows.map(c=>c.slot)).size!==12||rows.filter(c=>c.team===2).length!==6)return [];
 if(rows.some(c=>!Number.isInteger(c.slot)||c.slot<0||c.slot>23||![c.total,c.wallet].every(n=>Number.isInteger(n)&&n>=0&&n<=10000000)||c.wallet>c.total))return [];
 return rows.sort((a,b)=>a.hero-b.hero).map(c=>[c.hero,c.team,c.total,c.wallet]);
}
export function moneyClock(tick,r,basis='replay'){
 const total=r?.getField('m_pGameRules.m_nTotalPausedTicks'),paused=r?.getField('m_pGameRules.m_bGamePaused'),pauseStart=r?.getField('m_pGameRules.m_nPauseStartTick'),start=r?.getField('m_pGameRules.m_flGameStartTime');
 if(!Number.isInteger(tick)||tick<0||!Number.isInteger(total)||total<0||total>tick||!Number.isFinite(start)||start<=0)return NaN;
 // DEM packet ticks in replay are relative to game start; native pauseStart is absolute.
 if(paused){if(!Number.isInteger(pauseStart)||pauseStart<=0||pauseStart>tick+(basis==='broadcast'?0:start*64)+64)return NaN;return (pauseStart-total)/64-start;}
 return (tick-total)/64-(basis==='broadcast'?start:0);
}
export function attachMoney(parser,{basis='replay',maxSamples=21601}={}){
 const demo=parser.getDemo(),updates=[],kdaUpdates=[];let last=-1,overflow=false;
 parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET,p=>{
  const rules=demo.getEntitiesByClassName('CCitadelGameRulesProxy'),r=rules.length===1?rules[0]:null,clock=moneyClock(p.tick,r,basis);
  if(!Number.isFinite(clock)||clock<0)return;
  const second=Math.floor(clock);if(second===last){
   // Paused purchases may update the wallet without advancing the game second.
   if(basis==='broadcast'&&r.getField('m_pGameRules.m_bGamePaused')&&updates.length)updates[updates.length-1]={second,rows:([7,8].includes(r.getField('m_pGameRules.m_eGameState'))||(basis==='broadcast'&&r.getField('m_pGameRules.m_eGameState')===11))?controllerMoney(demo):[]};
   return;
  }
  if(second<last){updates.length=0;kdaUpdates.length=0;}
  last=second;const rows=([7,8].includes(r.getField('m_pGameRules.m_eGameState'))||(basis==='broadcast'&&r.getField('m_pGameRules.m_eGameState')===11))?controllerMoney(demo):[];
  updates.push({second,rows});kdaUpdates.push({second,rows:rows.length===12?controllerKDA(demo):[]});
  if(updates.length>maxSamples){if(basis==='broadcast'){updates.splice(0,updates.length-maxSamples);kdaUpdates.splice(0,kdaUpdates.length-maxSamples);}else{overflow=true;updates.length=0;kdaUpdates.length=0;}}
 });
 return {snapshot(){return {schema:1,columns:['hero','team','total','wallet'],supported:!overflow,updates:overflow?[]:updates.slice(),kda_updates:overflow?[]:kdaUpdates.slice()};}};
}

// Explicit sell=true only. ESold alone also occurs when an item is consumed by upgrades.
export function controllerKDA(demo){
 const cs=demo.getEntitiesByClassName('CCitadelPlayerController').filter(c=>c.active&&c.getField('m_nHeroID')>0&&[2,3].includes(c.getField('m_iTeamNum')));
 if(cs.length!==12||new Set(cs.map(c=>c.getField('m_nHeroID'))).size!==12||new Set(cs.map(c=>c.getField('m_unLobbyPlayerSlot'))).size!==12||cs.filter(c=>c.getField('m_iTeamNum')===2).length!==6)return [];
 const rows=cs.map(c=>[c.getField('m_nHeroID'),c.getField('m_iTeamNum'),c.getField('m_iPlayerKills'),c.getField('m_iDeaths'),c.getField('m_iPlayerAssists')]);
 return rows.every(v=>v.every(Number.isInteger)&&v.slice(2).every(n=>n>=0&&n<=1000))?rows.sort((a,b)=>a[0]-b[0]):[];
}
export function attachSales(parser,{basis='replay',maxEvents=basis==='broadcast'?512:20000}={}){
 const demo=parser.getDemo(),events=[];let pending=[],sequence=0,generation=0,previous=-1,overflow=false;
 parser.registerPostInterceptor(InterceptorStage.MESSAGE_PACKET,(p,m)=>{if(m.type===MessagePacketType.CITADEL_USER_MESSAGE_ITEM_PURCHASE_NOTIFICATION&&m.data.sell===true)pending.push({...m.data,tick:p.tick});});
 parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET,p=>{
  const rs=demo.getEntitiesByClassName('CCitadelGameRulesProxy'),r=rs.length===1?rs[0]:null,t=moneyClock(p.tick,r,basis),reset=basis==='broadcast'&&previous>=0&&(t<previous||p.type===DemoPacketType.DEM_FULL_PACKET);
  if(reset){events.length=0;generation++;}if(Number.isFinite(t))previous=t;
  const cs=demo.getEntitiesByClassName('CCitadelPlayerController').filter(c=>c.active&&c.getField('m_nHeroID')>0&&[2,3].includes(c.getField('m_iTeamNum'))),valid=cs.length===12&&new Set(cs.map(c=>c.getField('m_nHeroID'))).size===12&&cs.filter(c=>c.getField('m_iTeamNum')===2).length===6;
  const seen=new Set();for(const d of pending){
   if(reset||!valid||!Number.isFinite(t)||t<0||![7,8].includes(r?.getField('m_pGameRules.m_eGameState'))||r?.getField('m_pGameRules.m_bGamePaused')||!Number.isInteger(d.userid)||d.userid<0||d.userid>23||!Number.isInteger(d.abilityId)||d.abilityId<=0)continue;
   // Native userid is a controller index minus one, not m_unLobbyPlayerSlot.
   const owners=cs.filter(c=>c.index===d.userid+1),key=d.userid+'/'+d.abilityId+'/'+d.tick;if(owners.length!==1||seen.has(key))continue;seen.add(key);const c=owners[0];
   events.push({id:generation+'-'+(++sequence),sequence,generation,seconds:t,hero:c.getField('m_nHeroID'),team:c.getField('m_iTeamNum'),ability:d.abilityId,verified_sell:true});
  }pending=[];
  if(events.length>maxEvents){if(basis==='broadcast')events.splice(0,events.length-maxEvents);else{overflow=true;events.length=0;}}
 });
 return {snapshot(){return {schema:1,supported:!overflow,generation,events:overflow?[]:events.slice()};}};
}

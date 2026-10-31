import {InterceptorStage,MessagePacketType} from 'deadem';
import {moneyClock} from './money-parser.mjs';
// Native CMsgLaneColor enum: Yellow=1,Green=3,Blue=4,Purple=6.
// Keep each verified entity ID; no pair sum or inferred physical left/right.
export const GUARDIAN_LANES=[1,3,4,6];
export function guardianIndividuals(entities){
 const groups=new Map();
 for(const e of entities){if(e.class?.name!=='CNPC_BarrackBoss')continue;const team=e.getField('m_iTeamNum'),lane=e.getField('m_iLane'),hp=e.getField('m_iHealth'),max=e.getField('m_iMaxHealth'),life=e.getField('m_lifeState');
  if(![2,3].includes(team)||!GUARDIAN_LANES.includes(lane)||!Number.isInteger(e.handle)||e.handle<0||!Number.isInteger(hp)||!Number.isInteger(max)||max<=0||max>10000000||hp<0||hp>max||!Number.isInteger(life))continue;
  if(e.active===false&&hp>0&&life===0)continue;
  const key=team+'/'+lane;if(!groups.has(key))groups.set(key,{team,lane,rows:[]});groups.get(key).rows.push({id:e.handle,hp:life===0?hp:0,max});
 }
 const result=[];for(const {team,lane,rows} of groups.values()){if(rows.length>2||new Set(rows.map(x=>x.id)).size!==rows.length)continue;for(const row of rows)result.push([team,lane,row.id,row.hp,row.max]);}return result.sort((a,b)=>a[0]-b[0]||a[1]-b[1]||a[2]-b[2]);
}
export class GuardianCohort{
 constructor(){this.known=new Map();}
 update(entities,kills=[]){
  const present=new Set();for(const e of entities){if(e.class?.name!=='CNPC_BarrackBoss')continue;present.add(e.handle);this.known.set(e.handle,e);}
  for(const k of kills){const e=this.known.get(k.entityKilled);if(e&&e.getField('m_iTeamNum')===k.objectiveTeam){const fields=Object.fromEntries(['m_iTeamNum','m_iLane','m_iHealth','m_iMaxHealth','m_lifeState'].map(n=>[n,e.getField(n)]));fields.m_iHealth=0;fields.m_lifeState=1;this.known.set(e.handle,{class:{name:'CNPC_BarrackBoss'},handle:e.handle,active:false,getField:n=>fields[n]});}}
  const valid=[...this.known.values()].filter(e=>present.has(e.handle)||e.getField('m_iHealth')===0||e.getField('m_lifeState')>0);if(this.known.size>24)return [];
  return guardianIndividuals(valid);
 }
}
export function attachBaseGuardians(parser,{basis='replay',maxUpdates=21601}={}){
 const demo=parser.getDemo(),updates=[];let last=-1,overflow=false,cohort=new GuardianCohort(),kills=[];
 parser.registerPostInterceptor(InterceptorStage.MESSAGE_PACKET,(p,m)=>{if(m.type===MessagePacketType.CITADEL_USER_MESSAGE_BOSS_KILLED)kills.push(m.data);});
 parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET,p=>{const rs=demo.getEntitiesByClassName('CCitadelGameRulesProxy'),clock=moneyClock(p.tick,rs.length===1?rs[0]:null,basis);if(!Number.isFinite(clock)||clock<0)return;const second=Math.floor(clock);if(second===last)return;if(second<last){updates.length=0;cohort=new GuardianCohort();}last=second;
  updates.push({second,rows:cohort.update(demo.getEntitiesByClassName('CNPC_BarrackBoss'),kills)});kills=[];
  if(updates.length>maxUpdates){if(basis==='broadcast')updates.splice(0,updates.length-maxUpdates);else{overflow=true;updates.length=0;}}
 });return {snapshot(){return {schema:3,supported:!overflow,expected_per_lane:2,columns:['team','lane','entity','hp','max'],updates:overflow?[]:updates.slice()};}};
}

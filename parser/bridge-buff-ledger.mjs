import {readFileSync} from 'node:fs';
export const BRIDGE_RULES=JSON.parse(readFileSync(new URL('./data/bridge-buffs.json',import.meta.url),'utf8')).rules;
// Persistent state is separate from the three-second receipt ledger.
export class BridgeBuffLedger {
 constructor(rules=BRIDGE_RULES){this.rules=new Map(rules.map(r=>[r.hash,r]));this.slots=new Map();this.dead=new Set();this.signature=null;this.previous=null;this.state='waiting';this.metrics={};}
 reset(state='waiting'){this.slots.clear();this.dead.clear();this.signature=null;this.previous=null;this.state=state;}
 packet({seconds,gameStart,roster,gameState,full=false},changes,complete){
  const valid=Number.isFinite(seconds)&&seconds>=0&&Number.isFinite(gameStart)&&gameStart>0&&[7,8].includes(gameState)&&Array.isArray(roster)&&roster.length===12&&new Set(roster.map(p=>p.handle)).size===12&&new Set(roster.map(p=>p.hero)).size===12&&roster.every(p=>Number.isInteger(p.handle)&&p.handle>0&&Number.isInteger(p.hero)&&p.hero>0&&[2,3].includes(p.team)&&typeof p.alive==='boolean')&&roster.filter(p=>p.team===2).length===6;
  if(!valid){this.reset(gameState===11?'ended':'waiting');return [];}
  const signature=JSON.stringify([gameStart,...roster.map(p=>[p.handle,p.hero,p.team]).sort((a,b)=>a[0]-b[0])]);
  const discontinuity=this.previous!==null&&(seconds<this.previous||seconds-this.previous>2);
  const baseline=signature!==this.signature||discontinuity||full;
  if(baseline){const preserveDead=signature===this.signature&&!discontinuity;if(!preserveDead)this.dead.clear();this.slots.clear();if(typeof complete!=='function'){this.reset();return [];}changes=complete();this.signature=signature;}
  this.previous=seconds;this.state='ready';const owners=new Map(roster.map(p=>[p.handle,p]));
  for(const [id,row] of this.slots){const owner=owners.get(row.parent);if(!owner?.alive){this.dead.add(row.parent+'/'+row.serial+'/'+row.type);this.slots.delete(id);}else if(row.expires<=seconds)this.slots.delete(id);}
  for(const entry of changes||[]){
   if(!Number.isInteger(entry.id)||entry.id<0)continue;
   // A table slot can be reused without an explicit removal of its old value.
   this.slots.delete(entry.id);const v=entry.value;if(!v||v.entryType!==1)continue;
   const rule=this.rules.get(v.modifierSubclass),owner=owners.get(v.parent);if(!rule||!owner||!Number.isInteger(v.serialNumber)||v.serialNumber<0)continue;
   const key=v.parent+'/'+v.serialNumber+'/'+rule.type;if(!owner.alive){this.dead.add(key);continue;}if(this.dead.has(key))continue;
   const applied=v.lastAppliedTime-gameStart,expires=applied+v.duration;
   if(!Number.isFinite(applied)||applied<0||applied>seconds+.25||!Number.isFinite(v.duration)||v.duration<=0||v.duration>600||expires<=seconds)continue;
   this.slots.set(entry.id,{hero:owner.hero,parent:owner.handle,serial:v.serialNumber,type:rule.type,applied,expires});
  }
  if(this.slots.size>256||this.dead.size>4096){this.reset('capacity');return [];}
  const grouped=new Map();for(const row of this.slots.values()){if(row.expires<=seconds)continue;const key=row.parent+'/'+row.type;const prior=grouped.get(key);if(!prior||row.expires>prior.expires)grouped.set(key,row);}
  return [...grouped.values()].sort((a,b)=>a.hero-b.hero||a.applied-b.applied||a.type.localeCompare(b.type));
 }
}

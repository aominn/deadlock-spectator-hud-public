import {eligibleApplication} from './extract-replay-effects.mjs';
// Pure incremental receipt ledger. No network, game input, credentials, or HUD writes.
// Full snapshots and changes in ownership/clock establish a silent baseline.
export class LiveReceiptLedger {
 constructor(catalog,{guardSeconds=2,maxSeen=8192,maxEvents=512}={}) {
  this.catalog=catalog;this.guardSeconds=guardSeconds;this.maxSeen=maxSeen;this.maxEvents=maxEvents;
  this.seen=new Map();this.events=[];this.sequence=0;this.generation=0;this.signature=null;
  this.previous=null;this.stableAt=Infinity;this.metrics={};this.state='waiting';
 }
 count(key,n=1){this.metrics[key]=(this.metrics[key]||0)+n;}
 reset(reason){this.generation++;this.seen.clear();this.events=[];this.previous=null;this.stableAt=Infinity;this.count(reason);}
 packet({tick,tps=64,roster,gameStart,paused=false,gameState,pausedTicks=0,full=false},entries) {
  const time=(tick-pausedTicks)/tps;
  const valid=Number.isInteger(tick)&&tick>=0&&Number.isInteger(pausedTicks)&&pausedTicks>=0&&pausedTicks<=tick&&tps===64&&Number.isFinite(gameStart)&&gameStart>0&&Array.isArray(roster)&&roster.length===12&&
   new Set(roster.map(p=>p.handle)).size===12&&new Set(roster.map(p=>p.hero)).size===12&&
   roster.every(p=>Number.isInteger(p.handle)&&p.handle>0&&Number.isInteger(p.hero)&&p.hero>0&&[2,3].includes(p.team))&&
   roster.filter(p=>p.team===2).length===6&&roster.filter(p=>p.team===3).length===6;
  if(!valid){this.reset('invalid_context');this.signature=null;this.state='waiting';return [];}
  if(gameState===11){if(this.state!=='ended')this.reset('postgame');this.signature=null;this.state='ended';return [];}
  if(![7,8].includes(gameState)){this.reset('non_active_game');this.signature=null;this.state='waiting';return [];}
  if(paused){if(this.state!=='paused')this.reset('paused');this.signature=null;this.state='paused';return [];}
  const signature=JSON.stringify([gameStart,pausedTicks,...roster.map(p=>[p.handle,p.hero,p.team]).sort((a,b)=>a[0]-b[0])]);
  const changed=signature!==this.signature;
  const discontinuity=this.previous!==null&&(time<this.previous||time-this.previous>2);
  const baseline=changed||discontinuity||full||this.seen.size>=this.maxSeen;
  if(baseline){this.reset(changed?'ownership_baseline':full?'full_baseline':discontinuity?'clock_baseline':'capacity_baseline');this.signature=signature;this.stableAt=time+this.guardSeconds;}
  this.previous=time;this.state=time<this.stableAt?'baselining':'ready';
  const owners=new Map(roster.map(p=>[p.handle,p]));const fresh=[];
  for(const v of entries||[]) {
   const owner=owners.get(v.parent);
   if(!owner||!Number.isInteger(v.serialNumber)||v.serialNumber<0){this.count('unresolved_owner_or_serial');continue;}
   const key=v.parent+'/'+v.serialNumber;
   if(v.entryType===2){this.count('removals');continue;} // Keep tombstones: the same serial must not become a new receipt.
   if(v.entryType!==1){this.count('unknown_entry_type');continue;}
   if(this.seen.has(key)){if(this.seen.get(key)!==v.modifierSubclass)this.count('serial_path_conflict');else this.count('refresh_suppressed');continue;}
   if(this.seen.size>=this.maxSeen){this.count('capacity_suppressed');continue;}
   this.seen.set(key,v.modifierSubclass);
   if(baseline||time<this.stableAt){this.count('initial_or_guard_suppressed');continue;}
   const candidates=this.catalog.map.get(v.modifierSubclass)||[];
   if(candidates.length!==1){this.count('unmapped_or_collision');continue;}
   const known=candidates[0],approved=this.catalog.approved.get(known.path);
   if(!approved){this.count('outside_reviewed_scope');continue;}
   // Application timestamps already exclude pause ticks; normalize packet ticks only.
   // A HUD adapter must separately match native clock/route/roster before display.
   const age=time-v.lastAppliedTime;
   if(!Number.isFinite(age)||age<-.25||age>2){this.count('stale_or_future_application');continue;}
   const seconds=v.lastAppliedTime-gameStart;
   if(!Number.isFinite(seconds)||seconds<0){this.count('invalid_application_clock');continue;}
   const causes=this.catalog.abilities.get(v.abilitySubclass)||[],cause=causes.length===1?causes[0]:null;
   const caster=owners.get(v.caster);
   if(!eligibleApplication(this.catalog,known.path,owner,caster,causes.length===1?causes[0]:null)){this.count('self_movement_excluded');continue;}
   const event={sequence:++this.sequence,generation:this.generation,tick,seconds,hero:owner.hero,team:owner.team,parent:owner.handle,serial:v.serialNumber,
    path:known.path,native_class:known.native_class,cause,caster_hero:caster?.hero??null,caster_parent:caster?.handle??null,
    polarity:approved.polarity,effect:approved.effect,duration:v.duration,applied:v.lastAppliedTime,game_start:gameStart};
   fresh.push(event);this.events.push(event);this.count('receipts');
   if(this.events.length>this.maxEvents){this.events.shift();this.count('queue_evicted');}
  }
  return fresh;
 }
}

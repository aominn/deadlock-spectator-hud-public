import {attachBaseGuardians} from './base-guardian-parser.mjs';
import {attachEconomy} from './economy-parser.mjs';
import {attachMoney,attachSales} from './money-parser.mjs';
import {attachBridgeBuffs} from './bridge-buff-parser.mjs';
import {createReadStream,readFileSync,writeFileSync,statSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {Parser,ParserConfiguration,Logger,InterceptorStage,StringTableType,StringTableEvent,MessagePacketType} from 'deadem';
const localRoot=new URL('./data/',import.meta.url);
const read=p=>JSON.parse(readFileSync(new URL(p,localRoot),'utf8'));
export function source2Hash(text){const b=Buffer.from(text);const m=0x5bd1e995;let h=(0x31415926^b.length)>>>0,p=0;while(p+4<=b.length){let k=b.readUInt32LE(p);k=Math.imul(k,m)>>>0;k^=k>>>24;k=Math.imul(k,m)>>>0;h=(Math.imul(h,m)^k)>>>0;p+=4;}if(b.length-p>=3)h^=b[p+2]<<16;if(b.length-p>=2)h^=b[p+1]<<8;if(b.length-p>=1){h^=b[p];h=Math.imul(h,m)>>>0;}h^=h>>>13;h=Math.imul(h,m)>>>0;h^=h>>>15;return h>>>0;}
export function pawnIdentity(pawn){if(!pawn||!pawn.active||pawn.class.name!=='CCitadelPlayerPawn')return null;const ids=[...new Set([...pawn.fieldEntries()].filter(([k,v])=>(k==='m_nHeroID'||k.endsWith('.m_nHeroID'))&&Number.isInteger(v)&&v>0).map(x=>x[1]))];const team=pawn.getField('m_iTeamNum');return ids.length===1&&[2,3].includes(team)?{handle:pawn.handle,index:pawn.index,hero:ids[0],team}:null;}
export function exactCandidate(map,id){const rows=map.get(id)||[];return rows.length===1?rows[0]:null;}
export function buildCatalog(){
 const defs=read('modifier-definitions.json'),roots=read('modifiers-roots.json');
 const map=new Map(),byPath=new Map(),native=JSON.parse(readFileSync(new URL('./native-modifier-paths.json',import.meta.url),'utf8')).modifiers;
 const add=(key,record)=>{if(byPath.has(key)&&byPath.get(key).native_class===record.native_class)return;byPath.set(key,record);const h=source2Hash(key);if(!map.has(h))map.set(h,[]);map.get(h).push({path:key,...record});};
 for(const [key,d] of Object.entries(roots))add(key,{kind:'global',native_class:d._class});
 for(const d of native)add(d.path,{kind:'subclass',source:d.source,modifier:d.modifier,native_class:d._class});
 const abilities=new Map();for(const s of new Set(defs.map(d=>d.source))){const h=source2Hash(s);if(!abilities.has(h))abilities.set(h,[]);abilities.get(h).push(s);}
 const policy=JSON.parse(readFileSync(new URL('../engine/effect-policy.json',import.meta.url),'utf8')).modifiers;const approved=new Map(Object.entries(policy).filter(([path])=>byPath.has(path)));
 return {map,abilities,approved,collisions:[...map].filter(([,v])=>v.length>1).map(([hash,rows])=>({hash,paths:rows.map(x=>x.path)}))};
}
export function eligibleApplication(catalog,path,owner,caster,cause){
 const rule=catalog.approved.get(path);if(!rule)return false;
 if(rule.enemy_only&&caster&&(caster.handle===owner.handle||caster.team===owner.team))return false;
 if(rule.friendly_only&&(!caster||caster.team!==owner.team))return false;
 if(path==='modifier_citadel_knockdown'&&cause==='ability_deadpack_rocketeer'&&caster?.handle===owner.handle)return false;
 return true;
}
export async function extract(match,inputOverride=null){
 if(!/^\d{6,12}$/.test(match))throw Error('numeric match ID required');
 if(!inputOverride)throw Error('Explicit local replay path required');
 const input=inputOverride;
 const before=statSync(input),digest=createHash('sha256');for await(const chunk of createReadStream(input))digest.update(chunk);const sourceSha256=digest.digest('hex');
 const catalog=buildCatalog(),events=[],removals=[],roster=new Map(),active=new Map(),byPath={},perHero={},unmapped=new Map(),rejections={},warnings=[];
 let tick=0,success=false,error=null,updates=0,playerValues=0,refreshUpdates=0,initialEntries=0,rawClockCorrections=0;
 const reject=k=>rejections[k]=(rejections[k]||0)+1;
 const logger=new Logger({debug(){},info(){},trace(){},warn(x){if(warnings.length<5)warnings.push(String(x).slice(0,240));},error(x){throw Error(String(x));}});
 const parser=new Parser(new ParserConfiguration({entityClasses:['CCitadelPlayerPawn','CCitadelPlayerController','CCitadelGameRulesProxy','CItemXP','CNPC_BarrackBoss'],messagePacketTypes:[MessagePacketType.SVC_PACKET_ENTITIES,MessagePacketType.CITADEL_USER_MESSAGE_CURRENCY_CHANGED,MessagePacketType.CITADEL_USER_MESSAGE_HERO_KILLED,MessagePacketType.CITADEL_USER_MESSAGE_BOSS_KILLED,MessagePacketType.CITADEL_USER_MESSAGE_ITEM_PURCHASE_NOTIFICATION]}),logger),demo=parser.getDemo();
 parser.registerPreInterceptor(InterceptorStage.DEMO_PACKET,p=>{tick=p.tick;});
 const bridge=attachBridgeBuffs(parser,{pawnIdentity,basis:'replay'});
 const money=attachMoney(parser),sales=attachSales(parser);
 const economy=attachEconomy(parser);const baseGuardians=attachBaseGuardians(parser);
 demo.stringTableContainer.subscribe(StringTableEvent.TABLE_CHANGED,(_,table,entries)=>{
  if(table.type!==StringTableType.ACTIVE_MODIFIERS)return;updates++;
  const gameRules=demo.getEntitiesByClassName('CCitadelGameRulesProxy');
  const start=gameRules.length===1?gameRules[0].getField('m_pGameRules.m_flGameStartTime'):undefined;
  for(const entry of entries||[]){const v=entry.value;if(!v)continue;
   const pawn=demo.getEntityByHandle(v.parent),owner=pawnIdentity(pawn);if(!owner){reject(pawn?.class.name==='CCitadelPlayerPawn'?'ambiguous_hero':'not_resolved_player');continue;}
   playerValues++;roster.set(owner.handle,owner);
   const serialKey=owner.handle+'/'+v.serialNumber;
   if(v.entryType===2){const old=active.get(serialKey);if(old){removals.push({tick,hero:owner.hero,serial:v.serialNumber,parent:owner.handle,path:old.path});active.delete(serialKey);}continue;}
   if(v.entryType!==1){reject('unknown_entry_type');continue;}
   const known=exactCandidate(catalog.map,v.modifierSubclass);if(!known){unmapped.set(v.modifierSubclass,(unmapped.get(v.modifierSubclass)||0)+1);continue;}
   if(active.has(serialKey)){refreshUpdates++;const old=active.get(serialKey);if(old.path!==known.path)reject('serial_path_conflict');if(old.applied!==v.lastAppliedTime)rawClockCorrections++;continue;}
   active.set(serialKey,{path:known.path,applied:v.lastAppliedTime});
   if(!catalog.approved.has(known.path))continue;
   const row=catalog.approved.get(known.path),abilityCandidates=catalog.abilities.get(v.abilitySubclass)||[],cause=abilityCandidates.length===1?abilityCandidates[0]:null;
   if(!Number.isFinite(start)||start<=0||!Number.isFinite(v.lastAppliedTime)){reject('clock_not_resolved');continue;}
   const seconds=v.lastAppliedTime-start;if(seconds<0||tick<0){initialEntries++;continue;}
   const caster=pawnIdentity(demo.getEntityByHandle(v.caster));
   if(!eligibleApplication(catalog,known.path,owner,caster,cause)){reject('self_or_friendly_restriction_excluded');continue;}
   const event={tick,seconds,clock:Math.floor(seconds/60)+':'+String(Math.floor(seconds%60)).padStart(2,'0'),hero:owner.hero,team:owner.team,parent:owner.handle,pawn_index:owner.index,serial:v.serialNumber,path:known.path,native_class:known.native_class,modifier_hash:v.modifierSubclass,ability_hash:v.abilitySubclass,cause,caster_hero:caster?.hero??null,caster_parent:caster?.handle??null,polarity:row.polarity,effect:row.effect,duration:v.duration,applied:v.lastAppliedTime,game_start:start,meaning:'first active entry for exact parent handle and serial; refresh updates suppressed'};
   events.push(event);byPath[known.path]=(byPath[known.path]||0)+1;perHero[owner.hero]=(perHero[owner.hero]||0)+1;
  }
 });
 let timedOut=false;const begin=Date.now(),timer=setTimeout(()=>{timedOut=true;parser.abort();},60000);
 try{await parser.parse(createReadStream(input));if(timedOut)throw Error('replay parser deadline; incomplete result rejected');success=true;}catch(e){error=String(e);}finally{clearTimeout(timer);}
 await parser.dispose();const after=statSync(input);if(before.size!==after.size||before.mtimeMs!==after.mtimeMs){success=false;error='replay changed while reading';}
 const result={schema:2,source_sha256:sourceSha256,source_bytes:before.size,match,success,error,seconds_to_parse:(Date.now()-begin)/1000,package:'deadem@4.0.2',warnings,updates,player_values:playerValues,roster:[...roster.values()],events,removals,base_guardians:baseGuardians.snapshot(),bridge:bridge.snapshot(),money:{...money.snapshot(),sales:sales.snapshot()},economy:economy.snapshot(),counts:{approved_applications:events.length,refresh_updates_suppressed:refreshUpdates,changed_applied_time_updates:rawClockCorrections,initial_entries_suppressed:initialEntries,by_path:byPath,per_hero:perHero},rejections,unmapped:[...unmapped].sort((a,b)=>b[1]-a[1]).slice(0,50),hash_collisions:catalog.collisions,scope:'local replay file only; no upload, game connection, memory read or input; not proof of live coverage; source hash mapping and first-entry timestamps require runtime cross-check'};
 return result;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const match=process.argv[2];const result=await extract(match,process.argv[3]||null);writeFileSync(process.argv[4]||new URL('./replay-effects-'+match+'.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({success:result.success,error:result.error,match,seconds:result.seconds_to_parse,roster:result.roster.length,events:result.events.length,per_hero:result.counts.per_hero,collisions:result.hash_collisions.length}));if(!result.success)process.exitCode=1;}

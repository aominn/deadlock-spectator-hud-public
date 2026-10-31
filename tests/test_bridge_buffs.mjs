import assert from 'node:assert/strict';
import {BridgeBuffLedger,BRIDGE_RULES} from '../parser/bridge-buff-ledger.mjs';
const roster=Array.from({length:12},(_,i)=>({handle:100+i,hero:1+i,team:i<6?2:3,alive:true}));
const ctx={seconds:10,gameStart:1000,roster,gameState:7};
const entry=(id,kind=0,extra={})=>({id,value:{entryType:1,parent:100,serialNumber:id+1,modifierSubclass:BRIDGE_RULES[kind].hash,lastAppliedTime:1010,duration:160,...extra}});
let l=new BridgeBuffLedger();let rows=l.packet(ctx,[],()=>[entry(1),entry(2,1)]);assert.equal(rows.length,2);
rows=l.packet({...ctx,seconds:11},[{id:1,value:{entryType:1,modifierSubclass:0}}]);assert.equal(rows.length,1);assert.equal(rows[0].type,BRIDGE_RULES[1].type);
assert.equal(l.packet({...ctx,seconds:12},[{id:2,value:null}]).length,0);
l=new BridgeBuffLedger();rows=l.packet(ctx,[],()=>[entry(1),entry(2,0,{duration:170})]);assert.equal(rows.length,1);assert.equal(rows[0].expires,180);
rows=l.packet({...ctx,seconds:11},[entry(2,0,{lastAppliedTime:1009.75,duration:170})]);assert.equal(rows[0].expires,179.75);
rows=l.packet({...ctx,seconds:12,roster:roster.map((p,i)=>i===0?{...p,alive:false}:p)},[]);assert.equal(rows.length,0);
assert.equal(l.packet({...ctx,seconds:13},[entry(1),entry(2)]).length,0);
assert.equal(l.packet({...ctx,seconds:1,full:true},[],()=>[entry(1)]).length,0);
assert.equal(l.packet({...ctx,roster:roster.slice(1)},[]).length,0);
for(const bad of [{duration:-1},{duration:601},{lastAppliedTime:1100},{parent:999},{modifierSubclass:0},{serialNumber:-1}]){
 l=new BridgeBuffLedger();assert.equal(l.packet(ctx,[],()=>[entry(1,0,bad)]).length,0);
}
l=new BridgeBuffLedger();l.packet(ctx,[],()=>[entry(1),entry(2,1)]);
assert.equal(l.packet({...ctx,seconds:11},[{id:1,value:{entryType:2}}]).length,1);
assert.equal(l.packet({...ctx,seconds:171,full:true},[],()=>[entry(2,1)]).length,0);
assert.equal(l.packet({...ctx,gameState:11},[]).length,0);assert.equal(l.state,'ended');
console.log('bridge ledger: dual, reuse, null, refresh, expiry, death, seek, identity and invalid input passed');

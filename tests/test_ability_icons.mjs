import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../mod-src/spectator_probe.js',import.meta.url),'utf8');
const assets={};vm.createContext(assets);vm.runInContext(fs.readFileSync(new URL('../mod-src/asset-map.js',import.meta.url),'utf8'),assets);
const pairs=[['ヒル治療','Leech Therapy','leech'],['クリーピングテラー','Lurking Terrors','medicine_bag'],['ヒーリングニードル','Healing Needles','needle'],['カースドヴェイパー','Wretched Vapors','nurse_vapors']];
const funcs=(start,end)=>source.slice(source.indexOf('function '+start+'('),source.indexOf('function '+end+'('));
function panel(type,parent,id){const p={id,type,parent,children:[],style:{},SetImage(v){this.image=v;},FindChildTraverse(n){if(this.id===n)return this;for(const c of this.children){const hit=c.FindChildTraverse(n);if(hit)return hit;}return null;}};if(parent)parent.children.push(p);return p;}
const owner=panel('Panel',null,'owner');
const c={ULTIMATE_UNLOCK_SOURCE_VERIFIED:true,UNLOCK_SOURCE_VERIFIED:true,CARD_TOP:156,assets:assets.SpecNativeAssets,integer:s=>Number(s),text:p=>p?.text??'',all:(p,n)=>[{text:n==='ability_name'?p.name:'10'}],push:(s,kind,name,image,now,tier)=>s.queue.unshift({kind,name,image,tier,until:now+3}),auditCard:()=>{},$:{CreatePanel:panel,Msg:()=>{}}};
vm.createContext(c);vm.runInContext(funcs('card','playerSide')+funcs('splitName','remember')+funcs('push','purchases')+funcs('nativeUltimateUnlocked','auditCard')+funcs('renderCards','updateUrn'),c);
function player(name,tier){return {FindChildTraverse:n=>n==='AbilityButton1'?{name,BHasClass:k=>k==='Tier'+tier}:null};}
let cases=0;
for(const [jp,en,base] of pairs){
 const expected='s2r://panorama/images/hud/abilities/nurse/'+base+'_psd.vtex';
 assert.equal(c.assets.abilityNames[jp],expected);assert.equal(c.assets.abilityNames[en],expected);
 for(const name of [jp,en])for(const tier of [1,2,3]){
  const s={ready:true,abilities:[{tier:tier-1}],queue:[]};c.abilities(player(name,tier),s,100,false);assert.equal(s.queue.length,1);assert.equal(s.queue[0].image,expected);c.renderCards(owner,s,100);
  const card=c.card(owner,0),get=n=>card.FindChildTraverse(n);
  assert.equal(card.style.position,'0px 156px 0px');assert.equal(get('SpecEventIcon').image,expected);assert.equal(get('SpecEventName').text,name);assert.equal(get('SpecEventTierNumber').text,String(tier));assert.equal(get('SpecEventKind').visible,true);assert.equal(get('SpecEventKind').style.visibility,'visible');assert.equal(get('SpecEventName').style.maxWidth,'82px');
  c.abilities(player(name,tier),s,101,false);assert.equal(s.queue.length,1);c.renderCards(owner,s,104);assert.equal(card.visible,false);cases++;
 }
 const s={ready:true,abilities:[{tier:0}],queue:[]};c.abilities(player(jp,1),s,100,true);assert.equal(s.queue.length,0);
}
const card=c.card(owner,0),get=n=>card.FindChildTraverse(n),content=get('SpecEventContent');
assert.deepEqual(content.children.map(x=>x.id),['SpecEventIcon','SpecEventKind','SpecEventNameArea'],'requested reading order');
assert.equal(content.style.horizontalAlign,'center');assert.equal(content.style.verticalAlign,'center');assert.equal(content.style.width,'fit-children');assert.equal(content.style.flowChildren,'right');assert.equal(content.style.maxWidth,'124px');assert.equal((140-124)/2,8,'minimum side inset clears3px accent');
assert.equal(get('SpecEventIcon').style.marginRight,'4px');assert.equal(get('SpecEventIcon').style.width,'16px');assert.equal(get('SpecEventIcon').style.position,undefined,'no left2px fixed icon');assert.equal(get('SpecEventName').style.fontSize,'11px');assert.equal(get('SpecEventName').style.whiteSpace,'nowrap');
let layoutCases=0;
for(const kind of ['購入','強化','解放'])for(const hasImage of [true,false])for(const tier of [undefined,0,1,2,3,4]){
 const image=hasImage?(kind==='購入'?'s2r://panorama/images/items/weapon/test.vtex':'s2r://panorama/images/hud/abilities/nurse/needle_psd.vtex'):'';
 c.renderCards(owner,{queue:[{kind,name:'ヒーリングニードル',image,tier,until:103}]},100);
 layoutCases++;const hasTier=kind==='強化'&&tier>=1&&tier<=3,isUnlock=kind==='解放',width=Number(get('SpecEventName').style.maxWidth.replace('px',''));
 assert.equal(get('SpecEventKind').visible,hasTier||isUnlock);assert.equal(get('SpecEventTierNumber').text,hasTier?String(tier):'');assert.equal(get('SpecEventTierIcon').style.visibility,hasTier?'visible':'collapse');assert.equal(get('SpecEventUnlockIcon').style.visibility,isUnlock?'visible':'collapse');assert.equal(get('SpecEventIcon').visible,hasImage);assert.equal(width+(hasImage?20:0)+(isUnlock?18:hasTier?22:0),124,'bounded contents without overlap');assert.equal(get('SpecEventNameArea').style.maxWidth,width+'px');assert.equal(get('SpecEventNameArea').style.width,'fit-children');assert.equal(get('SpecEventName').style.horizontalAlign,'center');
}
const two={queue:[{kind:'強化',name:'ヒル治療',tier:3,image:'',until:103},{kind:'購入',name:'エクストラスピリット',image:'',until:103}]};c.renderCards(owner,two,100);assert.equal(c.card(owner,1).style.position,'0px 192px 0px');assert.equal(card.style.height,'32px');assert.equal(card.style.width,'140px');assert.equal(get('SpecEventTierNumber').text,'3');
vm.runInContext(funcs('urnBadge','teamResources'),c);c.playerSide=p=>p.side;
for(const [side,x] of [['left',18],['right',94]]){const badge={style:{}};c.urnBadge({side,actuallayoutwidth:140,FindChildTraverse:()=>badge});assert.equal(badge.style.position,x+'px -12px 0px');}
console.log(JSON.stringify({passed:true,upgrade_render_cases:cases,layout_cases:layoutCases,production_card_tree:true,reading_order:'icon + diamond tier + name',side_inset:8,internal_gap:4,unknown_tier_hidden:true,seek_and_repeat_guards:true,scope:'production functions/native fixtures;not native visual proof'}));

assert.equal(get('SpecEventTierIcon').image,'s2r://panorama/images/hud/hero_ability_pip_psd.vtex');
for(const node of ['SpecEventTierIcon','SpecEventTierNumber','SpecEventUnlockIcon','SpecEventName'])assert.equal(get(node).style.verticalAlign,'center');
assert.equal(get('SpecEventTierIcon').style.washColor,'#69e799');assert.equal(get('SpecEventTierNumber').style.color,'#69e799');assert.equal(get('SpecEventUnlockIcon').style.washColor,'#69e799');assert.equal(get('SpecEventName').style.height,'fit-children');assert.equal(c.eventColor({kind:'解放'}),'#69e799');assert.equal(c.eventColor({kind:'強化'}),'#69e799');
function observed(tier,trained){return {FindChildTraverse:n=>n==='AbilityButton1'?{name:'ヒル治療',BHasClass:k=>k==='Tier'+tier||(k==='not_trained'&&!trained)}:null};}
for(const tier of [0,1]){const s={ready:true,hero:'nurse',abilities:[{tier:0,trained:false}],queue:[]};c.abilities(observed(tier,true),s,100,false);assert.equal(s.queue.length,1);assert.equal(s.queue[0].kind,'解放');assert.equal(s.queue[0].image,c.assets.abilityNames['ヒル治療']);c.renderCards(owner,s,100);assert.equal(get('SpecEventUnlockIcon').style.visibility,'visible');assert.equal(get('SpecEventTierNumber').text,'');assert.equal(get('SpecEventName').style.maxWidth,'86px');c.abilities(observed(tier,true),s,101,false);assert.equal(s.queue.length,1);c.renderCards(owner,s,104);assert.equal(card.visible,false,'production4second duration');}
for(const [old,tier,trained,reset,ready] of [[{tier:0,trained:false},0,true,true,true],[{tier:0,trained:false},0,true,false,false],[{tier:0},0,true,false,true],[{tier:-1,trained:false},0,true,false,true],[{tier:0,trained:true},0,false,false,true],[{tier:0,trained:false},1,false,false,true],[{tier:2,trained:false},0,true,false,true]]){const s={abilities:[old],queue:[],ready};c.abilities(observed(tier,trained),s,100,reset);assert.equal(s.queue.length,0,'no baseline/unknown/downgrade/untrained false notification');}
const afterUnlock={ready:true,abilities:[{tier:0,trained:true}],queue:[]};c.abilities(observed(1,true),afterUnlock,102,false);assert.equal(afterUnlock.queue[0].kind,'強化');assert.equal(afterUnlock.queue[0].tier,1);
console.log('PASS native image badge geometry/green;observed unlocks;unknown/baseline guards;production4second lifetime;unlock/upgrade disambiguation');

assert(source.includes('var UNLOCK_SOURCE_VERIFIED=false;'),'unconfirmed unlock source stays off in shipped mod');c.UNLOCK_SOURCE_VERIFIED=false;const pending={ready:true,abilities:[{tier:0,trained:false}],queue:[]};c.abilities(observed(0,true),pending,100,false);assert.equal(pending.queue.length,0,'no unverified unlock notice in shipped configuration');

function ultimatePlayer(tier,unlocked,valid=true){return {BHasClass:k=>k==='UltimateUnlocked'&&unlocked,FindChildTraverse:n=>n==='UltimateStatus'?(valid?{}:null):n==='AbilityButton4'?{name:'カースドヴェイパー',BHasClass:k=>k==='Tier'+tier}:null};}
for(const tier of [0,1]){const s={hero:'87',ready:true,ultimateUnlocked:false,abilities:[null,null,null,{tier:0,trained:true}],queue:[]};c.abilities(ultimatePlayer(tier,true),s,383,false);assert.equal(s.queue.length,1);assert.equal(s.queue[0].kind,'解放');c.abilities(ultimatePlayer(1,true),s,384,false);assert.equal(s.queue.length,1,'delayed first tier does not duplicate unlock');c.abilities(ultimatePlayer(2,true),s,500,false);assert.equal(s.queue.length,2);assert.equal(s.queue[1].kind,'強化');assert.equal(s.queue[1].tier,2);c.renderCards(owner,s,383);assert.equal(get('SpecEventUnlockIcon').style.visibility,'visible');}
for(const [old,unlocked,tier,reset,ready,valid] of [[undefined,true,1,false,true,true],[false,true,1,true,true,true],[false,true,1,false,false,true],[true,true,1,false,true,true],[false,false,1,false,true,true],[false,true,1,false,true,false],[null,true,1,false,true,true]]){const s={ready,ultimateUnlocked:old,abilities:[null,null,null,{tier:0,trained:true}],queue:[]};c.abilities(ultimatePlayer(tier,unlocked,valid),s,383,reset);assert.equal(s.queue.length,0,'no join/seek/stale/unknown ultimate unlock');}
const delayed={ready:true,ultimateUnlocked:false,abilities:[null,null,null,{tier:0,trained:true}],queue:[]};c.abilities(ultimatePlayer(1,false),delayed,382,false);assert.equal(delayed.queue.length,0,'first tier before native lock change is not mislabeled upgrade');c.abilities(ultimatePlayer(1,true),delayed,383,false);assert.equal(delayed.queue.length,1);assert.equal(delayed.queue[0].kind,'解放');assert.equal(c.nativeUltimateUnlocked({FindChildTraverse:()=>null}),null);
console.log('PASS native UltimateUnlocked transition;independent from Tier0to1;later upgrades;join/seek/cooldown/unknown/delayed-update guards');

// Render shipped English notices with the native unlock icon and an optical name offset.
const english={};vm.createContext(english);vm.runInContext("var SpecIdentityData={items:{},heroes:{},abilities:{}};var $={Language:()=>\"english\",Localize:x=>x};"+fs.readFileSync(new URL('../mod-src/locale.js',import.meta.url),'utf8'),english);c.SpecLocale=english.SpecLocale;
const englishOwner=panel('Panel',null,'englishOwner');
for(const kind of ['購入','強化','解放'])for(const name of ['Spirit Strike','Shocking Reanimation','Improved Spirit Armor']){
 const image=kind==='購入'?'s2r://panorama/images/items/spirit/test.vtex':'s2r://panorama/images/hud/abilities/test.vtex';c.renderCards(englishOwner,{queue:[{kind,name,image,tier:2,until:103}]},100);const n=c.card(englishOwner,0),get=id=>n.FindChildTraverse(id),prefix=20+(kind==='解放'?18:kind==='強化'?22:0);assert.equal(get('SpecEventUnlock'),null,'no obsolete text badge');assert.equal(get('SpecEventUnlockIcon').style.visibility,kind==='解放'?'visible':'collapse');assert.equal(get('SpecEventUnlockIcon').image,'s2r://panorama/images/hud/unlock_icon.vsvg');assert.equal(get('SpecEventName').style.transform,'translateY(1px)');assert.equal(get('SpecEventName').text,name);assert.equal(get('SpecEventContent').style.width,'fit-children');assert.equal(get('SpecEventContent').style.horizontalAlign,'center');assert.equal(get('SpecEventNameArea').style.width,'fit-children');assert.equal(get('SpecEventName').style.maxWidth,(124-prefix)+'px');assert.equal(get('SpecEventName').style.whiteSpace,'nowrap');assert.equal(get('SpecEventKind').style.width,kind==='解放'?'14px':'18px');
}delete c.SpecLocale;console.log('PASS actual English locale notice tree: native unlock icon, name1px lower, compact centered group, bounded long names; internal Japanese event IDs unchanged');

c.renderCards(owner,{queue:[{kind:'解放',name:'ヒル治療',tier:0,image:'',until:103}]},100);assert.equal(get('SpecEventName').style.transform,'none','Japanese glyph optical position');assert.equal(get('SpecEventUnlockIcon').style.visibility,'visible');assert.equal(get('SpecEventUnlock'),null);

// Shared presentation contract: language changes content, not badge geometry.
const japan={};vm.createContext(japan);vm.runInContext("var SpecIdentityData={items:{},heroes:{},abilities:{}};var $={Language:()=>\"japanese\",Localize:x=>x};"+fs.readFileSync(new URL('../mod-src/locale.js',import.meta.url),'utf8'),japan);
for(const detail of [false,true])for(const hasImage of [false,true])for(const kind of ['購入','強化','解放']){
 const layouts=[];
 for(const locale of [japan.SpecLocale,english.SpecLocale]){c.SpecLocale=locale;const p=panel('Panel',null,'bilingual');c.detailCardTop=()=>220;c.renderCards(p,{queue:[{kind,name:locale.japanese?'ヒーリングニードル':'Healing Needles',image:hasImage?'s2r://panorama/images/hud/abilities/nurse/needle_psd.vtex':'',tier:2,until:103}]},100,detail,true);const n=c.card(p,0),get=id=>n.FindChildTraverse(id);layouts.push(JSON.stringify({card:n.style,content:get('SpecEventContent').style,badge:get('SpecEventKind').style,icon:get('SpecEventUnlockIcon').style,name:{...get('SpecEventName').style,transform:undefined},visible:get('SpecEventUnlockIcon').style.visibility}));}
 assert.equal(layouts[0],layouts[1],'JP/EN same geometry apart from measured font optical offset');
}delete c.SpecLocale;console.log('PASS12 bilingual pairs: normal/detail, image/none, purchase/upgrade/unlock; identical badge and name geometry apart from measured1px glyph offset');

for(const [locale,offset] of [[japan.SpecLocale,'none'],[english.SpecLocale,'translateY(1px)']])for(const detail of [false,true])for(const kind of ['購入','強化','解放']){c.SpecLocale=locale;const p=panel('Panel',null,'optical');c.detailCardTop=()=>220;c.renderCards(p,{queue:[{kind,name:locale.japanese?'アーケインサージ':'Arcane Surge',image:'',tier:2,until:103}]},100,detail,true);assert.equal(c.card(p,0).FindChildTraverse('SpecEventName').style.transform,offset);}delete c.SpecLocale;console.log('PASS measured Japanese optical offset,English position retained;normal/detail,all notice kinds');

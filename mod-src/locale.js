// Display language and exact identity aliases are prepared once, outside the HUD tick.
var SpecLocale=(function(){
'use strict';
var data=typeof SpecIdentityData==='undefined'?{items:{},heroes:{},abilities:{}}:SpecIdentityData;
var raw='';try{if(typeof $.Language==='function')raw=String($.Language()).toLowerCase();}catch(e){}
var japanese=raw==='japanese'||raw==='ja'||/^ja[-_]/.test(raw);
if(!raw){try{japanese=$.Localize('#upgrade_close_range')==='クローズクォーター';}catch(e){}}
var locale=japanese?'ja':'en',aliases=Object.create(null);
function key(v){return String(v||'').replace(/^\s+|\s+$/g,'').toLowerCase();}
function add(name,row){var k=key(name);if(!k)return;if(aliases[k]===undefined)aliases[k]=row;else if(aliases[k]!==row)aliases[k]=null;}
for(var id in data.items){var row=data.items[id];add(id,row);add(row.token,row);add(row.ja,row);add(row.en,row);try{var local=$.Localize('#'+row.token);if(local&&local!=='#'+row.token&&local!==row.token)add(local,row);}catch(e){}}
var statuses={};var statusTokens=[['Citadel_HUD_Impact_Stunned','stunned'],['Citadel_HUD_Impact_Silenced','silence_proc']];for(var z=0;z<statusTokens.length;z++){try{var value=$.Localize('#'+statusTokens[z][0]);if(value&&value.charAt(0)!=='#')statuses[value]=statusTokens[z][1];}catch(e){}}
var words={'解放':'Unlock','ミッドボス':'Mid Boss','ブリッジバフ':'Bridge Buff','出現中':'Alive','ヨーク':'York','ブロードウェイ':'Broadway','グリニッジ':'Greenwich','パープル':'Purple','レーン未取得':'Unknown lane','ガーディアン':'Guardian','ウォーカー':'Walker','ベースガーディアン':'Base Guardian','シュライン':'Shrine','パトロン':'Patron','弱体化パトロン':'Weakened Patron'};
return {language:locale,clientLanguage:raw,japanese:japanese,
 text:function(value){return japanese?value:(words[value]||value);},
 item:function(value){return aliases[key(value)]||null;},
 itemName:function(value){var row=aliases[key(value)];return japanese?value:row?row.en:(/^[\x20-\x7e]+$/.test(value)?value:'Item');},
 abilityName:function(hero,slot,value){var row=data.abilities[String(hero)+':'+String(slot)];return japanese?value:row?row.en:(/^[\x20-\x7e]+$/.test(value)?value:'Ability '+slot);},
 heroName:function(hero,value){var row=data.heroes[String(hero)];return japanese?value:row?row.en:(/^[\x20-\x7e]+$/.test(value)?value:'Hero');},
 statusKey:function(value){return statuses[value]||'';}
};
})();

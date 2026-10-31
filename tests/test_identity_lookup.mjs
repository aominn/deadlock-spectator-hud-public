import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../mod-src/spectator_probe.js',import.meta.url),'utf8'),ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(new URL('../mod-src/asset-map.js',import.meta.url),'utf8'),ctx);ctx.assets=ctx.SpecNativeAssets;
vm.runInContext(source.slice(source.indexOf('function abilityImage('),source.indexOf('function abilities(')),ctx);
let pairs=0;
for(const [hero,rows] of Object.entries(ctx.assets.abilities))for(let i=0;i<rows.length;i++){
 const row=rows[i];assert.equal(ctx.abilityImage(hero,i+1,row.name),ctx.assets.abilityNames[row.name],'Japanese behavior parity');assert.equal(ctx.abilityImage(hero,i+1,'unrecognized localized caption'),row.image);assert.equal(ctx.abilityImage(hero,i+1,''),row.image);pairs++;
}
assert.equal(ctx.abilityImage('unknown',1,'ヒル治療'),ctx.assets.abilityNames['ヒル治療']);assert.equal(ctx.abilityImage('unknown',1,'unknown'),'');assert.equal(ctx.abilityImage('87',0,'unknown'),'');assert.equal(ctx.abilityImage('87',5,'unknown'),'');assert(!source.includes('abilityUnlockProbe('));
console.log(JSON.stringify({passed:true,identity_pairs:pairs,caption_independent:true,japanese_parity:true,unknown_fallback:true,disabled_research_removed:true}));

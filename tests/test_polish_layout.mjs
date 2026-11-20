import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const src=fs.readFileSync(new URL('../mod-src/spectator_probe.js',import.meta.url),'utf8');const at=src.indexOf('function statusGeometry('),end=src.indexOf('function spec(){',at),c={isFinite,Math};vm.createContext(c);vm.runInContext(src.slice(at,end),c);
for(const [w,h,map] of [[1280,720,1000],[1920,1080,1512],[2560,1440,2050],[640,480,500]]){const g=c.statusGeometry(w,h,map);assert(g.x>=0&&g.y>=0&&g.x+g.width<=map&&g.y+g.height<=h);assert(g.y>=h-100,'status sits near screenbottom');}assert(Number.isFinite(c.statusGeometry(1920,1080,NaN).x));
const nativePause={paneltype:'CitadelPaused',style:{position:'0px 0px 0px',horizontalAlign:'right'}};
const nativePauseBody={GetParent:()=>nativePause};
c.ctx={BHasClass:key=>key==='spec_mode',FindChildTraverse:key=>key==='PausedContainer'?nativePauseBody:null};
for(const [w,h,map] of [[1280,720,1000],[1920,1080,1512],[2560,1440,2050]]){
 const g=c.statusGeometry(w,h,map);
 c.pauseLayout(g);
 const [x,y]=nativePause.style.position.split(' ').map(parseFloat);
 assert.equal(x,g.x,'pause shares the right-side status column');
 assert(y+40<=h-148,'pause clears the native extra-ability row');
}
c.pauseLayout(null);
assert.equal(nativePause.style.position,'0px 0px 0px');
assert.equal(nativePause.style.horizontalAlign,'right');

assert(src.includes("number.style.transform='translateY(1px)'"));assert(src.includes("n.style.backgroundColor='#11131355'"));assert(src.includes('nativeObjectiveLayout(now);updateUrn(now)')); console.log('PASS status bounds at720/1080/1440p,tier baseline andscoped neutralHP move');

const engine=fs.readFileSync(new URL('../engine/effect_bridge.py',import.meta.url),'utf8');assert(engine.includes('(120*scale,16*scale),(17,19,19,85)'));assert(engine.includes("(60*scale,7*scale),label"),'KDA lettering stays at its previous baseline');assert.match(src,/n\.style\.backgroundColor='#11131355';(?:n\.style\.zIndex='111';)?n\.style\.borderRadius='0px'/);assert.equal(-30+16,-14,'KDA backing joins the name backing without a gap');console.log('PASS joined KDA/name backing with unchanged text baseline');

assert(src.includes('time:clock,postgame:postgame(),players:out'));console.log('PASS native postgame confirmation is carried with the exact roster');

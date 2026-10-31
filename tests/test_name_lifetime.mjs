import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../mod-src/spectator_probe.js',import.meta.url),'utf8');
const nodes=[];
function panel(type,parent,id){const n={paneltype:type,id,parent,children:[],style:{},classes:new Set(),visible:true,valid:true,actualuiscale_x:1,actuallayoutwidth:type==='Label'||/^SpecHeroName\d+$/.test(id)?120:140,actuallayoutheight:type==='Label'?14:160,IsValid(){return this.valid;},IsVisible(){return this.valid&&this.visible&&(!this.parent||this.parent.IsVisible());},GetParent(){return this.parent;},GetPositionWithinWindow(){return {x:this.x||0,y:this.y||0};},FindChildTraverse(key){for(const c of this.children){if(c.id===key)return c;const f=c.FindChildTraverse(key);if(f)return f;}return null;}};if(parent)parent.children.push(n);nodes.push(n);return n;}
const root=panel('Panel',null,'root');root.actuallayoutwidth=1920;const ctx=panel('Panel',root,'ctx');
const c={ctx,nameOwners:[],namePanels:[],players:[],hidePlayerBadges:()=>{},Date,isFinite,Number,String,all:(p,k)=>p.children.filter(x=>x.classes.has(k)),text:n=>n&&n.text||'',state:p=>({hero:p.hero}),$:{CreatePanel:panel,Msg:()=>{}}};vm.createContext(c);vm.runInContext(source.slice(source.indexOf('function positionName('),source.indexOf('function playerName(')),c);
function owner(hero,x){const p=panel('CitadelHudTopBarPlayer',ctx,'p'+hero);p.hero=String(hero);p.x=x;p.y=54;const b=panel('Image',p,'HeroBadge');b.heroid=hero;b.actuallayoutwidth=88;b.actuallayoutheight=96;b.x=x+26;b.y=60;const n=panel('Label',p,'nativeName');n.classes.add('HeroName');n.text='キャラ'+hero;return p;}
function draw(ps){c.players=ps;c.refreshNameOwners();ps.forEach(p=>c.nameLabel(p,true));}
const visible=()=>nodes.filter(x=>x.valid&&x.visible&&/^SpecHeroName\d+$/.test(x.id));
const ps=Array.from({length:12},(_,i)=>owner(i+1,12+i*140));draw(ps);assert.equal(visible().length,12);for(let i=0;i<40;i++)draw(ps);assert.equal(c.namePanels.length,12);assert.equal(c.namePanels[0].parent,root);assert.equal(c.namePanels[0].style.width,'120px');assert.equal(c.namePanels[0].style.padding,'0px');assert.equal(c.namePanels[0].style.margin,'0px');assert.equal(c.namePanels[0].FindChildTraverse('Caption').style.horizontalAlign,'center');assert.equal(c.namePanels[0].FindChildTraverse('Caption').style.width,'fit-children');assert.equal(c.namePanels[0].FindChildTraverse('Caption').style.height,'fit-children');assert.equal(c.namePanels[0].FindChildTraverse('Caption').style.verticalAlign,'center');assert.equal(c.namePanels[0].style.overflow,'noclip');assert.equal(c.namePanels[0].style.position,'22px 40px 0px');
const extra=owner(86,896);extra.visible=false;draw([...ps,extra]);assert.equal(visible().length,12);extra.visible=true;extra.actuallayoutheight=0;draw([...ps,extra]);assert.equal(visible().length,12);extra.actuallayoutheight=NaN;draw([...ps,extra]);assert.equal(visible().length,12);extra.actuallayoutheight=160;extra.x=1970;extra.FindChildTraverse('HeroBadge').x=1996;draw([...ps,extra]);assert.equal(visible().length,12,'offscreen transient owner is excluded');
const old=ps[4];old.valid=false;ps[4]=owner(77,572);draw(ps);assert.equal(visible().length,12);assert(!visible().some(x=>x.FindChildTraverse('Caption').text==='キャラ5'),'orphan text cleared after owner replacement');
ps[2].visible=false;draw(ps);assert.equal(visible().length,11);ps[2].visible=true;draw(ps);assert.equal(visible().length,12);ps[2].FindChildTraverse('nativeName').text='更新後のキャラ';draw(ps);assert(visible().some(x=>x.FindChildTraverse('Caption').text==='更新後のキャラ'));
c.hideNames();assert.equal(visible().length,0);draw(ps);assert.equal(visible().length,12);
for(const p of ps)p.valid=false;draw([]);assert.equal(visible().length,0,'empty roster clears all old names');
const next=Array.from({length:12},(_,i)=>owner(i+100,12+i*140));draw(next);assert.equal(visible().length,12);assert(visible().every(x=>/^キャラ1\d\d$/.test(x.FindChildTraverse('Caption').text)));assert.equal(c.namePanels.length,12,'new match reuses same12 panels');
const thirteenth=owner(999,800);draw([...next,thirteenth]);assert.equal(visible().length,0,'ambiguous13validowners must not publish wrong names');draw(next);assert.equal(visible().length,12);
root.actualuiscale_x=2;for(const p of next){p.actualuiscale_x=2;const b=p.FindChildTraverse('HeroBadge');b.actualuiscale_x=2;b.x=p.x+52;}draw(next);assert.equal(c.namePanels.length,12);
assert(source.includes('refreshNameOwners();}'));assert(source.includes('function hide(){restoreObjectiveLayout();hideNames();hidePlayerBadges();'));
console.log('PASS bounded12 pooled labels;hidden/zero/NaN/offscreen ignored;deleted owner and full roster replacement;mode hide/resume;ambiguous13hidden;native geometry;scale');

// Physical positions and UI units must describe the same center at multiple scales.
for(const scale of [1,1.25,2]){
 const badge={actualuiscale_x:scale,actuallayoutwidth:88,GetPositionWithinWindow:()=>({x:38*scale,y:60*scale})};
 const owner={GetPositionWithinWindow:()=>({x:12*scale,y:54*scale}),FindChildTraverse:()=>badge};
 const parent={actualuiscale_x:scale,GetPositionWithinWindow:()=>({x:0,y:0})};
 const label={actualuiscale_x:scale,actuallayoutwidth:120};const g=c.positionName(owner,parent,label,-14,120);
 assert.equal(g.x,22);assert.equal(g.y,40);assert.equal(g.center,82);assert.equal(g.width,120);
}
console.log('PASS fixed name box centers at1x,1.25x,2x without character-specific offsets');

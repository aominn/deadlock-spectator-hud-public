from pathlib import Path
import struct,zlib,json,hashlib,re
r=Path(__file__).resolve().parent.parent/'mod-src'
items=[(r/'native-base'/name,css) for name,css in [('citadel_hud_top_bar.vcss_c','debug-override.css'),('hud_data_feed.vcss_c','feed-override.css'),('citadel_hud_active_player_stats.vcss_c','bonus-override.css'),('citadel_base_styles.vcss_c','toast-override.css'),('hud_ability_icon.vcss_c','detail-ability-override.css'),('citadel_mods_purchased_panel.vcss_c','detail-inventory-override.css')]]
entries=[];proof=[]
def blocks(raw):
 t=8+struct.unpack_from('<I',raw,8)[0];result=[]
 for i in range(struct.unpack_from('<I',raw,12)[0]):
  at=t+i*12;k=raw[at:at+4];off,n=struct.unpack_from('<II',raw,at+4);result.append((k,raw[at+4+off:at+4+off+n]))
 return result
for source,cssfile in items:
 raw=source.read_bytes();css=(r/cssfile).read_text(encoding='utf-8-sig');clean=re.sub(r'/\*.*?\*/','',css,flags=re.S)
 assert all(x.strip().split('{')[0].strip().startswith('.spec_mode') for x in clean.split('}') if '{' in x)
 assert not any(x in css.lower() for x in ['http','javascript','@import','script:'])
 old=blocks(raw);new=list(old);i=next(i for i,b in enumerate(old) if b[0]==b'DATA');data=old[i][1];pos=6
 for _ in range(struct.unpack_from('<H',data,4)[0]):pos=data.index(b'\0',pos)+9
 text=data[pos:]+b'\n'+css.encode();new[i]=(b'DATA',struct.pack('<I',zlib.crc32(text)&0xffffffff)+data[4:pos]+text)
 out=bytearray(raw[:16]);struct.pack_into('<II',out,8,8,len(new));out+=bytearray(12*len(new))
 for j,(kind,body) in enumerate(new):
  out+=b'\0'*((-len(out))%16);start=len(out);at=16+j*12;out[at:at+4]=kind;struct.pack_into('<II',out,at+4,start-at-4,len(body));out+=body
 struct.pack_into('<I',out,0,len(out));assert blocks(out)==new
 assert all(new[j]==b for j,b in enumerate(old) if b[0]!=b'DATA')
 target=r/'compiled/panorama/styles'/source.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(out)
 entries.append((source.stem,bytes(out)));proof.append(dict(source=str(source),source_sha256=hashlib.sha256(raw).hexdigest(),compiled_sha256=hashlib.sha256(out).hexdigest(),preserved_non_data=True,css=cssfile,scoped=True))
import sys; sys.path.insert(0,str(r))
from panorama_writer import layout,script,vpk
files={'panorama/styles/'+name+'.vcss_c':body for name,body in entries}
for path,fn,src in [('panorama/layout/citadel_hud_top_bar.vxml_c',layout,'citadel_hud_top_bar.xml'),('panorama/scripts/spectator_probe.vjs_c',script,'spectator_probe.js'),('panorama/layout/citadel_hud_hero_shop.vxml_c',layout,'citadel_hud_hero_shop.xml'),('panorama/layout/hud_escape_menu.vxml_c',layout,'hud_escape_menu.xml')]:
 data=(r/src).read_bytes();data=(b''.join((r/name).read_bytes() for name in ['asset-map.js','identity-data.js','locale.js'])+data) if src=='spectator_probe.js' else data;body=fn('panorama/'+('layout/' if src.endswith('.xml') else 'scripts/')+src,data);files[path]=body;target=r/'compiled'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
 proof.append(dict(source=src,compiled_sha256=hashlib.sha256(body).hexdigest(),method='reviewed local writer; primary MIT format reference'))
vpk=vpk(files);(r/'pak99_dir.vpk').write_bytes(vpk)
result=dict(resources=proof,vpk_sha256=hashlib.sha256(vpk).hexdigest(),archive_roundtrip=False,scope='spectator native HUD plus fixed loopback PNG from local read-only snapshot companion; no memory hooks')
(r/'build-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


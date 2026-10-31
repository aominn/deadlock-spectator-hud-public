"""Populate ignored development assets from a verified local generation, without changing source metadata."""
from pathlib import Path
import argparse,json,re,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from asset_prepare import safe,member,digest,PreparationError

def populate(generated,root):
 generated=safe(generated);root=safe(root)
 proof=json.loads((generated/'local-preparation-proof.json').read_text(encoding='utf-8'))
 recipe=json.loads((root/'tools/local-assets-recipe.json').read_text(encoding='utf-8'))
 if not proof.get('passed') or proof.get('scope')!='local-game-assets' or proof.get('generated_vpk_sha256')!=recipe['expected_vpk_sha256']:raise PreparationError('Generation does not match this source')
 for name,expected in proof['files'].items():
  if digest(safe(generated/member(name)).read_bytes())!=expected:raise PreparationError('Generated file changed: '+name)
 layouts={'mod-src/citadel_hud_top_bar.xml','mod-src/citadel_hud_hero_shop.xml','mod-src/hud_escape_menu.xml'}
 copied=[]
 for row in recipe['outputs']:
  name=member(row['destination'])
  if not (re.fullmatch(r'engine/icons/[a-zA-Z0-9_-]+\.png',name) or re.fullmatch(r'mod-src/native-base/[a-z0-9_]+\.vcss_c',name) or name in layouts):raise PreparationError('Unexpected development asset: '+name)
  src=safe(generated/name)
  if not src.is_file():continue
  if name not in proof['files']:raise PreparationError('Unverified development asset: '+name)
  target=safe(root/name);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target);copied.append(name)
 return {'passed':True,'copied':len(copied),'source_metadata_unchanged':True}

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--generated',required=True);args=ap.parse_args()
 print(json.dumps(populate(args.generated,Path(__file__).resolve().parents[1])))

"""Install locally generated assets while preserving the original package manifest."""
from pathlib import Path
from contextlib import contextmanager
import json,shutil,uuid
from manager_core import Refused,safe,member,sha,read_json,save
PROFILE={'schema':1,'recipe':'asset-preparation/recipe.json','template':'asset-preparation/template','reader':'asset-preparation/reader/HudAssetReader.exe'}

def require_profile(manifest):
 if manifest.get('asset_preparation')!=PROFILE:raise Refused('素材準備方式が未対応です。')
 required=['engine/asset_prepare.py','engine/asset_install.py',PROFILE['recipe'],PROFILE['reader'],PROFILE['template']+'/engine/effect-catalog.json',PROFILE['template']+'/tools/build_mod.py',PROFILE['template']+'/mod-src/panorama_writer.py']
 if any(n not in manifest['files'] for n in required):raise Refused('素材準備用のファイルが不足しています。')
 if any(n.startswith('engine/icons/') or n=='mod/pak01_dir.vpk' or n.endswith(('.vtex_c','.vsvg_c','.vcss_c','.vxml_c','.vpk')) for n in manifest['files']):raise Refused('素材を含まない配布形式と内容が一致しません。')
 return PROFILE

def source_manifest(root,manifest):
 if manifest.get('asset_preparation'):
  require_profile(manifest);return manifest,(root/'release.json').read_bytes()
 prepared=manifest.get('prepared_assets',{})
 if prepared.get('schema')!=1 or prepared.get('source')!='source-release.json' or 'source-release.json' not in manifest['files']:raise Refused('画像を更新するための元データがありません。')
 raw=(root/'source-release.json').read_bytes()
 if sha(raw)!=prepared.get('source_sha256'):raise Refused('素材準備の元データが一致しません。')
 original=json.loads(raw);require_profile(original)
 for n,h in original['files'].items():
  if n!='engine/effect-catalog.json' and manifest['files'].get(n)!=h:raise Refused('素材準備のプログラムが変更されています。')
 return original,raw

@contextmanager
def prepared_bundle(manager,root,manifest,game,previous=None):
 from asset_prepare import prepare
 root=safe(root);original,original_raw=source_manifest(root,manifest);recipe=read_json(root/PROFILE['recipe']);parent=manager.home/'staging';parent.mkdir(parents=True,exist_ok=True);work=safe(parent/('.assets-'+uuid.uuid4().hex));work.mkdir()
 try:
  try:proof=prepare(game,root/PROFILE['recipe'],root/PROFILE['template'],root/PROFILE['reader'],work/'generated',flexible=True,previous=previous)
  except ValueError as exc:raise Refused('標準UIや素材準備用ファイルが対応していません。現在の版とゲーム設定は変更していません。対応するHUDへ更新してください。') from exc
  bundle=work/'bundle';bundle.mkdir()
  for n in original['files']:
   if n=='engine/effect-catalog.json':continue
   src=safe(root/member(n));out=bundle/n;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
  generated=work/'generated'
  for f in (generated/'engine').rglob('*'):
   if f.is_file():out=bundle/'engine'/f.relative_to(generated/'engine');out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,out)
  out=bundle/'mod/pak01_dir.vpk';out.parent.mkdir(exist_ok=True);shutil.copy2(generated/'mod-src/pak99_dir.vpk',out)
  report={k:proof[k] for k in ['image_policy','image_counts','images','critical_resources','native_sha256','generated_vpk_sha256']};report.update({'schema':1,'source_sha256':sha(original_raw)});save(bundle/'asset-report.json',report);(bundle/'source-release.json').write_bytes(original_raw)
  m=dict(original);m.pop('asset_preparation');m['prepared_assets']={'schema':1,'source':'source-release.json','source_sha256':sha(original_raw),'report':'asset-report.json'};m['files']={f.relative_to(bundle).as_posix():sha(f.read_bytes()) for f in sorted(bundle.rglob('*')) if f.is_file()};save(bundle/'release.json',m);manager.verify(bundle)
  yield bundle,report
 finally:
  safe(work)
  for f in work.rglob('*'):safe(f)
  if work.parent!=safe(parent) or not work.name.startswith('.assets-'):raise Refused('一時準備先が一致しません。')
  shutil.rmtree(work)

def asset_summary(root,manifest):
 if not manifest.get('prepared_assets'):return None
 p=manifest['prepared_assets'];report=read_json(safe(root/p['report']));return report['image_counts']

def compatible(root,manifest,game):
 from asset_prepare import critical_compatible
 try:
  p=manifest.get('prepared_assets',{});report=read_json(safe(root/p['report']));recipe=read_json(safe(root/PROFILE['recipe']));expected={x['asset']:x['sha256'] for x in recipe['resources'].values() if x['mode'] in ('raw','text')}
  return report['critical_resources']==expected and report['generated_vpk_sha256']==recipe['expected_vpk_sha256'] and critical_compatible(game,report)
 except (OSError,ValueError,KeyError,TypeError):return False

def install_ready(manager,bundle,game,previous,original_config):
 """Switch only after generation succeeds; restore the previous config/mount on error."""
 from manager_core import Manager
 enabled=original_config.get('enabled',False);next_manager=Manager(manager.home,bundle,busy=manager.busy)
 try:
  if enabled:manager.normal()
  result=next_manager.setup(game);c=next_manager.config();c['previous_bundle']=original_config.get('previous_bundle') if previous and Path(result['bundle'])==Path(previous) else (str(previous) if previous else None);save(next_manager.config_file,c)
  if enabled:next_manager.enable()
  manager.bundle=Path(result['bundle']);return result
 except Exception as error:
  try:
   if (manager.home/'mount.json').exists():next_manager.normal()
   restore=dict(original_config);restore['enabled']=False;save(manager.config_file,restore)
   if enabled and previous:Manager(manager.home,previous,busy=manager.busy).enable()
  except Exception as recovery:raise Refused('更新を停止しました。復旧状態を確認してください：'+str(recovery)) from error
  raise Refused('更新できなかったため、元の版と設定を維持しました：'+str(error)) from error

def refresh_assets(manager):
 manager.idle();c=manager.config()
 if not c.get('bundle') or not c.get('game'):raise Refused('先に初回セットアップを行ってください。')
 root=safe(c['bundle']);m=manager.verify(root)
 if not m.get('prepared_assets') and not m.get('asset_preparation'):raise Refused('この版は画像の自動準備に未対応です。新しい配布版を適用してください。')
 with prepared_bundle(manager,root,m,c['game'],previous=root) as (bundle,report):
  result=install_ready(manager,bundle,c['game'],root,c);result['assets']=report['image_counts'];result['message']='画像を更新しました。取得できない画像は旧画像または画像なしで継続します。';return result


def adopt_bundle(manager):
 """Apply a newer extracted release; preserve user config and the previous version."""
 from manager_core import Manager
 manifest=manager.verify();config=manager.config()
 if not config.get('bundle') or not config.get('game'):return {'updated':False}
 current=manager.verify(config['bundle'])
 def version(value):
  main,_,suffix=value.partition('-');return (*map(int,main.split('.')),not bool(suffix),suffix)
 if version(manifest['version'])<=version(current['version']):return {'updated':False}
 manager.idle()
 previous=config['bundle']
 if manifest.get('asset_preparation'):
  with prepared_bundle(manager,manager.bundle,manifest,config['game'],previous=previous) as (bundle,report):
   result=install_ready(manager,bundle,config['game'],previous,config);result['assets']=report['image_counts']
 else:result=install_ready(manager,manager.bundle,config['game'],previous,config)
 result.update(updated=True,message='新しい版へ更新しました。設定を引き継いで開き直します。')
 return result

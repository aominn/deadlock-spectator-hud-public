"""Local-only asset preparation trial. Never modifies game files or active config.

The recipe contains references/checksums and XML edits, not native images/styles/layouts.
A separate public-distribution review is required; this is not a grant of game rights.
"""
from pathlib import Path, PureWindowsPath
import base64,hashlib,io,json,os,shutil,stat,struct,subprocess,sys,tempfile,zlib

class PreparationError(ValueError): pass

def digest(data): return hashlib.sha256(data).hexdigest()
def safe(path):
 p=Path(path).absolute()
 if '..' in p.parts:raise PreparationError('Parent traversal refused')
 for q in (p,*p.parents):
  if q.exists() and (q.is_symlink() or getattr(q.lstat(),'st_file_attributes',0)&1024):raise PreparationError('Linked path refused')
 return p

def member(name):
 if not isinstance(name,str) or not name or '\\' in name or ':' in name or PureWindowsPath(name).is_absolute():raise PreparationError('Invalid member')
 if any(x in ('','.','..') or x.endswith((' ','.')) or any(ord(c)<32 or c in '<>"|?*' for c in x) or (os.path.isreserved(x) if hasattr(os.path,'isreserved') else PureWindowsPath(x).is_reserved()) for x in name.split('/')):raise PreparationError('Unsafe member')
 return name

def inside(path,root):
 try:Path(path).relative_to(root);return True
 except ValueError:return False

class GameArchive:
 def __init__(self,game):
  self.game=safe(game);index=safe(self.game/'pak01_dir.vpk')
  if index.stat().st_size>64*1024**2:raise PreparationError('VPK index too large')
  d=index.read_bytes()
  if len(d)<12:raise PreparationError('VPK header truncated')
  sig,version,size=struct.unpack_from('<III',d);self.header=28 if version==2 else 12
  if sig!=0x55aa1234 or version not in (1,2) or size>len(d)-self.header:raise PreparationError('Unsupported VPK header')
  self.end=self.header+size;pos=self.header;self.entries={};folds=set()
  def string():
   nonlocal pos
   end=d.find(b'\0',pos,self.end)
   if end<0 or end-pos>4096:raise PreparationError('VPK string truncated')
   text=d[pos:end].decode('utf-8');pos=end+1;return text
  while True:
   ext=string()
   if not ext:break
   while True:
    folder=string()
    if not folder:break
    while True:
     name=string()
     if not name:break
     if pos+18>self.end:raise PreparationError('VPK entry truncated')
     crc,pre,arch,offset,length,term=struct.unpack_from('<IHHIIH',d,pos);pos+=18
     if term!=65535 or pos+pre>self.end:raise PreparationError('VPK preload malformed')
     path=member((folder+'/' if folder!=' ' else '')+name+'.'+ext)
     if path.casefold() in folds:raise PreparationError('Duplicate VPK member')
     folds.add(path.casefold());self.entries[path]=(crc,arch,offset,length,d[pos:pos+pre]);pos+=pre
  if pos!=self.end:raise PreparationError('VPK tree trailing bytes')
 def read(self,path,expected=None):
  member(path)
  if not path.startswith(('panorama/images/','panorama/styles/','panorama/layout/')):raise PreparationError('Resource outside HUD scope')
  if not path.endswith(('.vtex_c','.vsvg_c','.vcss_c','.vxml_c')):raise PreparationError('Resource type refused')
  if path not in self.entries:raise PreparationError('Game resource missing: '+path)
  crc,arch,offset,length,pre=self.entries[path]
  if length+len(pre)>32*1024**2:raise PreparationError('Resource too large')
  f=safe(self.game/('pak01_dir.vpk' if arch==32767 else 'pak01_%03d.vpk'%arch));start=offset+(self.end if arch==32767 else 0)
  if start+length>f.stat().st_size:raise PreparationError('Resource out of bounds')
  with f.open('rb') as stream:stream.seek(start);raw=pre+stream.read(length)
  if len(raw)!=length+len(pre) or zlib.crc32(raw)&0xffffffff!=crc:raise PreparationError('Resource CRC mismatch')
  if expected is not None and digest(raw)!=expected:raise PreparationError('Untested game resource; update preparation recipe: '+path)
  return raw

def splice(source,operations):
 if not isinstance(operations,list) or len(operations)>10000:raise PreparationError('Invalid splice recipe')
 chunks=[];total=0
 for op in operations:
  if set(op)=={'copy'}:
   offset,length=op['copy']
   if type(offset)!=int or type(length)!=int or min(offset,length)<0 or offset+length>len(source):raise PreparationError('Splice range out of bounds')
   part=source[offset:offset+length]
  elif set(op)=={'text'} and isinstance(op['text'],str):part=op['text'].encode('utf-8')
  else:raise PreparationError('Invalid splice operation')
  total+=len(part)
  if total>2*1024**2:raise PreparationError('Layout too large')
  chunks.append(part)
 return b''.join(chunks)

def verify_tree(root,files):
 root=safe(root);found={f.relative_to(root).as_posix() for f in root.rglob('*') if f.is_file()}
 if found!=set(files):raise PreparationError('Unexpected template/reader files')
 for n,h in files.items():
  f=safe(root/member(n))
  if digest(f.read_bytes())!=h:raise PreparationError('Preparation input changed: '+n)

def valid_png(body,required_size=None):
 from PIL import Image
 if not isinstance(body,bytes) or not 0<len(body)<=4*1024**2:raise PreparationError('PNG size')
 with Image.open(io.BytesIO(body)) as im:
  if im.format!='PNG' or im.width<1 or im.height<1 or max(im.size)>2048 or im.width*im.height>4194304 or getattr(im,'n_frames',1)!=1:raise PreparationError('PNG format/dimensions')
  if required_size and im.size!=required_size:raise PreparationError('PNG target dimensions')
  im.load()
 return body

def choose_image(current,previous=None,resize=None):
 """Current readable PNG, then same-identity saved PNG, then no image."""
 from PIL import Image
 try:
  body=valid_png(current)
  if resize:
   with Image.open(io.BytesIO(body)) as image:im=image.convert('RGBA').resize(resize,Image.Resampling.LANCZOS);buf=io.BytesIO();im.save(buf,format='PNG');body=buf.getvalue()
  return body,'current'
 except (OSError,ValueError,TypeError,Image.DecompressionBombError):pass
 try:return valid_png(previous,resize),'previous'
 except (OSError,ValueError,TypeError,Image.DecompressionBombError):return None,'missing'

class PreviousImages:
 def __init__(self,root=None):
  self.root=None;self.files={};self.catalog={}
  if root:
   try:self.root=safe(root);self.files=json.loads(safe(self.root/'release.json').read_text(encoding='utf-8-sig'))['files'];raw=self.read('engine/effect-catalog.json');self.catalog=json.loads(raw) if raw else {}
   except (OSError,ValueError,KeyError,TypeError):self.root=None;self.files={};self.catalog={}
 def read(self,name):
  try:
   if not self.root or name not in self.files:return None
   f=safe(self.root/member(name))
   if f.stat().st_size>8*1024**2:return None
   raw=f.read_bytes();return raw if digest(raw)==self.files[name] else None
  except (OSError,ValueError,TypeError):return None
 def sale(self,ability,source):
  try:
   row=self.catalog['sale_items'][ability]
   if row['source']!=source:return None
   return base64.b64decode(row.get('icon_png') or '',validate=True)
  except (KeyError,TypeError,ValueError):return None

def prepare(game,recipe_file,template,reader,output,*,flexible=False,previous=None):
 recipe=json.loads(safe(recipe_file).read_text(encoding='utf-8'));template=safe(template);reader=safe(reader);output=safe(output);game=safe(game)
 if recipe.get('schema')!=1 or not 0<len(recipe.get('resources',{}))<=1000:raise PreparationError('Unsupported recipe')
 if output.exists() or not output.parent.is_dir():raise PreparationError('Use a new folder in an existing parent')
 for root in [game,template,reader.parent]:
  if inside(output,root) or inside(root,output):raise PreparationError('Output must be separate from game and preparation inputs')
 verify_tree(template,recipe['template_sha256']);verify_tree(reader.parent,recipe['reader_files'])
 if digest(reader.read_bytes())!=recipe['reader_sha256']:raise PreparationError('Reader changed')
 archive=GameArchive(game);raws={};unavailable={};native_hashes={};critical={};images=[]
 for key,row in recipe['resources'].items():
  if not isinstance(key,str) or len(key)!=20 or any(c not in '0123456789abcdef' for c in key) or row['mode'] not in ['png','text','raw','svg-png']:raise PreparationError('Invalid resource recipe')
  image=flexible and row['mode'] in ('png','svg-png')
  try:raws[key]=archive.read(row['asset'],None if image else row['sha256']);native_hashes[row['asset']]=digest(raws[key])
  except (OSError,ValueError) as exc:
   if not image:raise
   unavailable[key]=type(exc).__name__
  if not image:critical[row['asset']]=row['sha256']
 destinations=[member(x['destination']) for x in recipe['outputs']]
 if len(destinations)!=len(set(n.casefold() for n in destinations)):raise PreparationError('Duplicate output')
 old=PreviousImages(previous);temporary=Path(tempfile.mkdtemp(prefix='.hud-assets-',dir=output.parent));payload=temporary/'payload';payload.mkdir();decoded=temporary/'decoded';decoded.mkdir();inputs=temporary/'inputs';inputs.mkdir()
 try:
  jobs=[]
  for key,raw in raws.items():
   row=recipe['resources'][key];src=inputs/(key+Path(row['asset']).suffix);src.write_bytes(raw)
   if row['mode']!='raw':jobs.append({'input':str(src),'output':str(decoded/key),'mode':row['mode']})
  def decode(batch,optional):
   if not batch:return
   jobfile=temporary/('optional-jobs.json' if optional else 'jobs.json');jobfile.write_text(json.dumps(batch),encoding='utf-8')
   command=[str(reader)] if reader.suffix.lower()=='.exe' else ['dotnet',str(reader)]
   try:
    result=subprocess.run(command+[str(jobfile)],capture_output=True,encoding='utf-8',timeout=180,creationflags=0x08000000 if os.name=='nt' else 0)
    if result.returncode and not optional:raise PreparationError('Asset decoder failed: '+result.stderr[-1000:])
   except (OSError,subprocess.TimeoutExpired):
    if not optional:raise PreparationError('Asset decoder could not start or timed out')
  if flexible:
   decode([j for j in jobs if j['mode']=='text'],False);decode([j for j in jobs if j['mode']!='text'],True)
  else:decode(jobs,False)
  for key,row in recipe['resources'].items():
   if row['mode']=='raw':continue
   if flexible and row['mode'] in ('png','svg-png'):continue
   f=decoded/key
   if not f.is_file() or digest(f.read_bytes())!=row['decoded_sha256']:raise PreparationError('Decoded resource differs: '+row['asset'])
  for name in recipe['template_sha256']:
   out=payload/member(name);out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(template/name,out)
  def current(key):
   try:return (decoded/key).read_bytes()
   except OSError:return None
  for row in recipe['outputs']:
   key=row['resource'];action=row['action'];image=row['destination'].startswith('engine/icons/')
   if flexible and image:
    body,state=choose_image(current(key),old.read(row['destination']),resize=(64,64) if action=='resize64' else None);images.append({'id':row['destination'],'state':state,'asset':recipe['resources'][key]['asset']})
    if body is None:continue
   else:
    body=raws[key] if action=='raw' else current(key)
    if action=='splice':body=splice(body,row['splices'])
    elif action=='resize64':body,state=choose_image(body,resize=(64,64))
    elif action not in ['raw','copy']:raise PreparationError('Invalid output action')
    if row.get('expected_sha256') and digest(body)!=row['expected_sha256']:raise PreparationError('Generated output differs: '+row['destination'])
   out=payload/member(row['destination']);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(body)
  catalog_file=payload/'engine/effect-catalog.json';catalog=json.loads(catalog_file.read_text(encoding='utf-8'))
  for row in recipe['sale_icons']:
   item=catalog['sale_items'][row['ability']];body,state=choose_image(current(row['resource']),old.sale(row['ability'],item['source']) if flexible else None,resize=(24,24))
   if not flexible and (body is None or digest(body)!=row['expected_png_sha256']):raise PreparationError('Sale icon differs')
   item['icon_png']=base64.b64encode(body).decode('ascii') if body else None
   if flexible:images.append({'id':'sale:'+row['ability'],'state':state,'asset':recipe['resources'][row['resource']]['asset']})
  catalog_file.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  if not flexible and digest(catalog_file.read_bytes())!=recipe['catalog_expected_sha256']:raise PreparationError('Generated catalog differs')
  built=subprocess.run([sys.executable,'-B','-I',str(payload/'tools/build_mod.py')],capture_output=True,encoding='utf-8',timeout=40,creationflags=0x08000000 if os.name=='nt' else 0)
  if built.returncode:raise PreparationError('Local MOD generation failed: '+built.stderr[-1000:])
  if digest((payload/'mod-src/pak99_dir.vpk').read_bytes())!=recipe['expected_vpk_sha256']:raise PreparationError('Generated MOD differs')
  counts={name:sum(x['state']==name for x in images) for name in ['current','previous','missing']}
  proof={'passed':True,'scope':'local-game-assets','resources':len(raws),'icons':sum(x['destination'].startswith('engine/icons/') for x in recipe['outputs']),'sale_icons':len(recipe['sale_icons']),'generated_vpk_sha256':recipe['expected_vpk_sha256'],'source_crc_and_sha256_checked':not flexible,'critical_resources':critical,'native_sha256':native_hashes,'game_files_written':False,'requires_installed_dotnet_for_this_trial':reader.suffix.lower()!='.exe','recipe_sha256':digest(Path(recipe_file).read_bytes()),'image_policy':'current/previous/none' if flexible else 'strict','image_counts':counts,'images':images,'files':{f.relative_to(payload).as_posix():digest(f.read_bytes()) for f in sorted(payload.rglob('*')) if f.is_file()}}
  (payload/'local-preparation-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');os.rename(payload,output);return proof
 finally:
  safe(temporary)
  for item in temporary.rglob('*'):safe(item)
  if not inside(temporary,output.parent) or not temporary.name.startswith('.hud-assets-'):raise PreparationError('Temporary path refused')
  shutil.rmtree(temporary)

def critical_compatible(game,proof):
 try:
  rows=proof['critical_resources']
  if not isinstance(rows,dict) or len(rows) not in (9,12):return False
  archive=GameArchive(game)
  for asset,expected in rows.items():archive.read(asset,expected)
  return True
 except (OSError,ValueError,KeyError,TypeError):return False

def main():
 import argparse
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ['game','recipe','template','reader','output']:ap.add_argument('--'+name,required=True)
 ap.add_argument('--flexible',action='store_true');ap.add_argument('--previous');args=ap.parse_args()
 try:
  proof=prepare(args.game,args.recipe,args.template,args.reader,args.output,flexible=args.flexible,previous=args.previous);print(json.dumps({k:v for k,v in proof.items() if k not in ('files','images','native_sha256')},ensure_ascii=False))
 except Exception as exc:print(json.dumps({'passed':False,'error':str(exc)},ensure_ascii=False));sys.exit(1)
if __name__=='__main__':main()

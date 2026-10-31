"""Prepare vendor runtime from fixed official HTTPS artifacts, without installing globally."""
from pathlib import Path,PureWindowsPath
import argparse,hashlib,io,json,urllib.request,zipfile

def safe_name(n):
 p=PureWindowsPath(n)
 if not n or p.drive or p.is_absolute() or '\\' in n or ':' in n or any(x in ('','.','..') for x in n.split('/')):raise ValueError('unsafe vendor member')
 return n

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args();root=Path(__file__).resolve().parent;lock=json.loads((root/'runtime-lock.json').read_text(encoding='utf-8'));out=Path(a.output).absolute()
 if out.exists():raise ValueError('Choose a new vendor output folder')
 data={}
 for name in ['python','pillow']:
  row=lock[name];raw=urllib.request.urlopen(row['url'],timeout=45).read(64*1024**2+1)
  if len(raw)>64*1024**2 or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError(name+' official artifact hash mismatch')
  data[name]=raw
 out.mkdir(parents=True)
 for name,raw in data.items():
  base=out if name=='python' else out/'Lib/site-packages';base.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   for info in z.infolist():
    if info.is_dir():continue
    n=safe_name(info.filename)
    if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('linked vendor member')
    f=base/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(info))
 pins={f.relative_to(out).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.rglob('*')) if f.is_file()};(out/'vendor-manifest.json').write_text(json.dumps({'sources':{n:lock[n] for n in ['python','pillow']},'files':pins},indent=2),encoding='utf-8');print(json.dumps({'python':lock['python']['version'],'pillow':lock['pillow']['version'],'files':len(pins),'official_hashes_verified':True}))
if __name__=='__main__':main()

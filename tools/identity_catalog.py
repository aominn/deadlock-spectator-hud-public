"""Offline identity catalog for future language support. Never loaded by the HUD loop.

Explicit installed-game localization inputs only; generated names stay on that PC.
Unknown/ambiguous aliases resolve to nothing, never a guessed item.
"""
from pathlib import Path
import argparse,hashlib,json,re

def alias_key(name):return name.strip().casefold()

def localization_tokens(text):
 # Read exact token/value lines; refuse conflicting duplicate keys.
 result={}
 for key,value in re.findall(r'^\s*"([^"\r\n]+)"\s+"([^"\r\n]*)"',text,re.M):
  if not key.startswith('upgrade_') or key.endswith('_search'):continue
  if key in result and result[key]!=value:raise ValueError('Conflicting localization token: '+key)
  result[key]=value
 return result

def build_catalog(catalog,assets,locales):
 items={};aliases={lang:{} for lang in locales};abilities={}
 for identity,row in catalog['sale_items'].items():
  if not re.fullmatch(r'[1-9][0-9]{0,9}',identity) or int(identity)>0xffffffff:raise ValueError('Invalid item ID')
  internal=row['source']
  if not re.fullmatch(r'upgrade_[a-z0-9_]+',internal):raise ValueError('Invalid internal item name')
  names={lang:tokens[internal] for lang,tokens in locales.items() if tokens.get(internal)}
  images={assets['items'][n] for n in [row.get('name'),*names.values()] if n in assets['items']}
  items[identity]={'id':identity,'internal':internal,'names':names,'image':next(iter(images)) if len(images)==1 else None,'image_basis':'existing-name-map' if len(images)==1 else None}
  for lang,name in names.items():aliases[lang].setdefault(alias_key(name),[]).append(identity)
 for hero,slots in assets['abilities'].items():
  for slot,row in enumerate(slots,1):abilities[hero+':'+str(slot)]={'hero':hero,'slot':slot,'source_name':row['name'],'image':row['image']}
 for lang in aliases:
  for key in aliases[lang]:aliases[lang][key].sort(key=int)
 return {'schema':1,'items':items,'abilities':abilities,'aliases':aliases,'conflicts':{lang:{k:v for k,v in rows.items() if len(v)>1} for lang,rows in aliases.items()}}

def resolve_item(catalog,language,name):
 candidates=catalog['aliases'].get(language,{}).get(alias_key(name),[])
 return catalog['items'][candidates[0]] if len(candidates)==1 else None

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ['catalog','asset-map','english','japanese','output']:ap.add_argument('--'+name,required=True)
 q=ap.parse_args();out=Path(q.output)
 if out.exists():raise ValueError('Use a new output file')
 paths={n:Path(getattr(q,n.replace('-','_'))) for n in ['catalog','asset-map','english','japanese']};raws={n:f.read_bytes() for n,f in paths.items()};script=raws['asset-map'].decode('utf-8-sig');prefix='var SpecNativeAssets = '
 if not script.startswith(prefix):raise ValueError('Unexpected asset map')
 assets=json.loads(script[len(prefix):].strip().removesuffix(';'));result=build_catalog(json.loads(raws['catalog']),assets,{lang:localization_tokens(raws[name].decode('utf-8-sig')) for lang,name in [('en','english'),('ja','japanese')]});result['input_sha256']={n:hashlib.sha256(v).hexdigest() for n,v in raws.items()}
 with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'items':len(result['items']),'abilities':len(result['abilities']),'conflicts':result['conflicts']},ensure_ascii=False))
if __name__=='__main__':main()

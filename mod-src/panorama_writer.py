# Source 2 layout/script writer. KV3 v5 and AST format adapted from modlock (MIT); see THIRD-PARTY-LICENSE.txt.
import struct,zlib,xml.etree.ElementTree as ET,re
U=lambda n:struct.pack('<I',n&0xffffffff)
def pad(b,a):return b+b'\0'*((-len(b))%a)
def literals(b):
 n=len(b);h=bytes([min(n,15)<<4]);rest=n-15
 if n>=15:
  h+=bytes([255])*(rest//255)+bytes([rest%255])
 return h+b
def kv3(value):
 strings={};order=[];types=bytearray();lengths=bytearray();b4=bytearray();objects=0;arrays=0
 def text(s):
  if not s:return -1
  if s not in strings:strings[s]=len(order);order.append(s)
  return strings[s]
 def walk(v):
  nonlocal objects,arrays
  if v is None:types.append(1)
  elif isinstance(v,bool):types.append(13 if v else 14)
  elif isinstance(v,str):types.append(6);b4.extend(U(text(v)))
  elif isinstance(v,int):types.append(11 if -2147483648<=v<=2147483647 else 12);b4.extend(U(v))
  elif isinstance(v,list):
   arrays+=1;types.append(8);b4.extend(U(len(v)))
   for x in v:walk(x)
  elif isinstance(v,dict):
   objects+=1;types.append(9);lengths.extend(U(len(v)))
   for k,x in v.items():b4.extend(U(text(k)));walk(x)
  else:raise TypeError(type(v))
 walk(value);raw=b''.join(s.encode()+b'\0' for s in order);nstrings=len(raw);first=pad(raw,4)+U(len(order));second=bytes(lengths+b4+types)+U(0xffeedd00);f=literals(first);s=literals(second)
 out=U(0x4b563305)+bytes.fromhex('7c161274e9069846aff2e63eb59037e7')+U(1)+struct.pack('<HH',0,16384)
 out+=b''.join(U(n) for n in [nstrings,1,0,len(types)])+struct.pack('<HH',objects,arrays)
 out+=b''.join(U(n) for n in [len(first)+len(second),len(f)+len(s),0,0,0,0,len(first),len(f),len(second),len(s),0,0,len(b4)//4,0,0,objects,arrays,0]);assert len(out)==120
 return out+f+s
def resource(version,blocks):
 out=bytearray(struct.pack('<IHHII',0,12,version,8,len(blocks)))+bytearray(12*len(blocks))
 for i,(tag,body) in enumerate(blocks):
  out=bytearray(pad(out,16));at=16+12*i;start=len(out);out[at:at+4]=tag.encode();struct.pack_into('<II',out,at+4,start-at-4,len(body));out.extend(body)
 struct.pack_into('<I',out,0,len(out));return bytes(out)
def metadata(compiler,version,path,source):
 return kv3(dict(m_InputDependencies=[dict(m_RelativeFilename=path,m_SearchPath='citadel',m_nFileCRC=zlib.crc32(source),m_bOptional=False,m_bFileExists=True,m_bIsGameFile=True)],m_AdditionalInputDependencies=[],m_ArgumentDependencies=[],m_SpecialDependencies=[dict(m_String='Panorama Layout Compiler Version' if compiler=='CompilePanorama' else 'JavaScript Compiler Version',m_CompilerIdentifier=compiler,m_nFingerprint=version,m_nUserData=0)],m_SpecialInputDependencies=[],m_AdditionalRelatedFiles=[],m_ChildResourceList=[],m_WeakReferenceList=[],m_SearchableUserData=dict(IsChildResource=0),m_SubassetReferences=None,m_SubassetDefinitions=None))
def ref(s):
 if s.startswith('s2r://'):return dict(eType='REFERENCE_COMPILED',name=s[6:])
 m=re.fullmatch(r'file://\{resources\}/(.*)\.(\w+)',s)
 if m:return dict(eType='REFERENCE_COMPILED',name='panorama/'+m[1]+'.v'+m[2]+'_c')
 return dict(eType='REFERENCE_PASSTHROUGH',name=s.removeprefix('file://'))
def node(e):
 children=[node(x) for x in e];tag=e.tag
 if tag=='include':return dict(eType='INCLUDE',child=ref(e.get('src')),sourceLineColumn=[1,1])
 if tag=='script':return dict(eType='SCRIPT_BODY',name=e.text or '',sourceLineColumn=[1,1])
 if tag=='root':d=dict(eType='ROOT')
 elif tag in ['styles','scripts','snippets']:d=dict(eType=tag.upper())
 elif tag=='snippet':d=dict(eType='SNIPPET',name=e.get('name'))
 else:
  d=dict(eType='PANEL',name=tag);attrs=[]
  for k,v in e.attrib.items():
   val=ref(v) if v.startswith(('s2r://','file://')) else dict(eType='PANEL_ATTRIBUTE_VALUE',**({'name':v} if v else {}))
   attrs.append(dict(eType='PANEL_ATTRIBUTE',name=k,child=val))
  children=attrs+children
 if len(children)==1:d['child']=children[0]
 elif children:d['vecChildren']=children
 d['sourceLineColumn']=[] if tag=='root' else [1,1];return d
def layout(path,source):
 tree=node(ET.fromstring(source));return resource(3,[('RED2',metadata('CompilePanorama',14,path,source)),('DATA',struct.pack('<IH',zlib.crc32(source),0)),('LaCo',kv3(dict(m_AST=dict(m_pRoot=tree))))])
def script(path,source):return resource(4,[('RED2',metadata('CompileJavaScript',4,path,source)),('DATA',source)])
def vpk(files):
 groups={}
 for path,body in sorted(files.items()):
  folder,base=path.rsplit('/',1);name,ext=base.rsplit('.',1);groups.setdefault(ext,{}).setdefault(folder,[]).append((name,body))
 tree=b'';payload=b''
 for ext,folders in groups.items():
  tree+=ext.encode()+b'\0'
  for folder,entries in folders.items():
   tree+=folder.encode()+b'\0'
   for name,body in entries:tree+=name.encode()+b'\0'+struct.pack('<IHHIIH',zlib.crc32(body),0,32767,len(payload),len(body),65535);payload+=body
   tree+=b'\0'
  tree+=b'\0'
 tree+=b'\0';return struct.pack('<III',0x55aa1234,1,len(tree))+tree+payload


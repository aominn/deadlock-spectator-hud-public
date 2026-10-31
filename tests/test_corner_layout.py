from pathlib import Path
import sys,io,json,os
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'));import effect_bridge as b
for canvas in (1920,2560):
 players=[]
 for side in (0,1):
  start=(canvas-1812)/2+(972 if side else 0)
  for i in range(6):players.append({'hero':'0','pos':{'x':start+i*140+(-42 if side==0 else 42),'y':46},'width':140,'cards':[]})
 def overlap(a,z):return a[0]<z[0]+z[2] and z[0]<a[0]+a[2] and a[1]<z[1]+z[3] and z[1]<a[1]+a[3]
 portraits=[(p['pos']['x']+26,46,88,100) for p in players]
 urns=[(p['pos']['x']+(18 if i<6 else 94),34,28,32) for i,p in enumerate(players)]
 assert all(x>=0 and x+w<=canvas for x,y,w,h in portraits+urns),'portrait or urn outside screen'
 wealth=(canvas/2-80,54,160,26);advantage=(canvas/2-172,16,344,28)
 for cards_count in (0,1,2):
  for p in players:p['cards']=[[p['pos']['x']+3,230+j*62,134,58] for j in range(cards_count)]
  obstacles=b.card_obstacles(players,canvas);assert len(obstacles)==cards_count*12
  assert all(x>=15 and x+w<=canvas-15 for x,y,w,h in obstacles),'purchase cards cross safe screen margins'
  rects=[]
  for i,p in enumerate(players):
   x,y,width,side=b.corner_geometry(p,canvas);assert side==('left' if i<6 else 'right')
   assert y==46,'status top aligns with portrait top'
   assert width==38 and x>=0 and x+width<=canvas;previous=y-2
   for lane in range(4):
    top=b.clear_receipt_top(x,max(y+lane*b.NOTICE_PITCH,previous+2),width,b.NOTICE_HEIGHT,obstacles);previous=top+b.NOTICE_HEIGHT;rect=(x,top,width,b.NOTICE_HEIGHT)
    assert not any(overlap(rect,z) for z in portraits),'receipt overlaps portrait'
    assert not any(overlap(rect,z) for z in urns),'receipt overlaps urn'
    assert not overlap(rect,wealth) and not overlap(rect,advantage),'receipt overlaps team resources'
    assert not overlap(rect,(canvas/2-65,96,130,34)),'receipt overlaps centered rejuvenator group'
    assert not any(overlap(rect,z) for z in obstacles),'receipt overlaps active purchase/ability card'
    assert rect[1]+rect[3]<=420,'all4 status slots must remain inside the image'
    assert not any(overlap(rect,z) for z in rects),'receipt lanes overlap'
    rects.append(rect)
  assert len(rects)==48
  # Native ultimate, two held bridge icons and personal rejuvenator stay in each cell.
  icon_rects=[]
  for i,p in enumerate(players):
   center=p['pos']['x']+70
   row=[(center-10,171,20,20),(center+(12 if i<6 else -32),171,20,20)]
   row.extend(b.bridge_geometry(p,j,canvas) for j in (0,1))
   for icon in row:
    assert not any(overlap(icon,z) for z in icon_rects),'status icons from adjacent players overlap'
    assert not any(overlap(icon,z) for z in rects),'status icon overlaps receipt'
    icon_rects.append(icon)
   assert not any(overlap(row[u],row[v]) for u in range(4) for v in range(u+1,4)),'own status icons overlap'
 # Invalid supplied geometry cannot move or grow the overlay arbitrarily.
 bad={**players[0],'cards':[[0,0,float('nan'),20],[-1,0,20,20],[0,0,99999,20]]}
 assert not b.card_obstacles([bad],canvas)
 old={k:v for k,v in players[0].items() if k!='cards'}
 assert len(b.card_obstacles([old],canvas))==2,'older heartbeat conservatively reserves2 cards'
assert b.font_at(15).getname()[0]=='Noto Sans JP'
for polarity in ('buff','debuff'):
 tag,label,icon=b.paint_receipt({'source':'native_status','modifier':'stunned','effect':'スタン','polarity':polarity})
 assert tag.getpixel((3,24))[3]>0 and tag.getpixel((37,33))[3]==0
 assert tag.getpixel((5,2))==(24,25,24,210),'backing extends behind the icon'
clock=[100.5]
with patch.object(b.time,'monotonic',lambda:clock[0]):
 b.S=b.State();s=b.S;s.last_clock=600;s.last_http=100.5;s.native_at=100.5
 native=list(dict.fromkeys(b.CAT['heroes'].items()));picked=[]
 for name,hero in native:
  if hero not in [h for _,h in picked]:picked.append((name,hero))
  if len(picked)==12:break
 for i,(name,hero) in enumerate(picked):
  s.entities[i+1]=name;players[i]['hero']=str(hero)
  row=b.resolve_world([{'classes':['stunned','isDebuff']}])[0]
  s.notifications[i+1]={str(j):{**row,'started':100,'until':103,'clock':'10:00','lane':j} for j in range(4)}
 data={'width':2560,'time':'10:00','players':players}
 im=Image.open(io.BytesIO(b.render(data)));assert im.getbbox()
 x,y,width,_=b.corner_geometry(players[0],2560)
 assert im.getpixel((x+width-1,y))[3]==0 and im.getpixel((x+width-1,y+b.NOTICE_HEIGHT-1))[3]==0,'panel corners/background must remain transparent'
 alpha=im.getchannel('A');assert sum(1 for v in alpha.get_flattened_data() if v)>0
 im.save(Path(os.environ['SPEC_TEST_ARTIFACT_DIR'])/'synthetic-four-per-player.png')
 clock[0]=102.88;s.native_at=clock[0];s.last_http=clock[0]
 faded=Image.open(io.BytesIO(b.render(data)));assert max(faded.getchannel('A').get_flattened_data())<255,'single final fade, not flashing'
 clock[0]=103.01;s.native_at=clock[0];s.last_http=clock[0]
 assert Image.open(io.BytesIO(b.render(data))).getbbox() is None
print(json.dumps({'players':12,'slots_per_player':4,'no_portrait_urn_wealth_purchase_overlap':True,'no_surrounding_frame':True,'icon_only_backing':True,'expires_without_lingering':True,'synthetic_only':True}))

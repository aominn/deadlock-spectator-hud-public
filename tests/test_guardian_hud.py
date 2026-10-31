from pathlib import Path
import sys,unittest,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from base_guardian_hud import GuardianView
class GuardianTests(unittest.TestCase):
 def data(self,t,hp=8000,maximum=8000):return dict(schema=3,supported=True,expected_per_lane=2,columns=['team','lane','entity','hp','max'],updates=[dict(second=t,rows=[[2,1,101,hp,maximum],[3,1,201,8000,8000]])])
 def test_damage_sum_and_boundaries(self):
  v=GuardianView();self.assertEqual(v.sample(self.data(1),1,1,'a'),[])
  rows=v.sample(self.data(2,4000),2,2,'a');self.assertEqual(rows[0]['fraction'],.5);self.assertEqual(rows[0]['lane'],1)
  self.assertTrue(v.sample(self.data(3,4000),3,6.999,'a'));self.assertFalse(v.sample(self.data(4,4000),4,7,'a'))
  self.assertEqual(v.sample(self.data(5,5000),5,8,'a'),[],'healing isnot hit');self.assertEqual(v.sample(self.data(1,1000),1,9,'a'),[],'rewind baseline');self.assertEqual(v.sample(self.data(2,900),2,10,'b'),[],'newscope baseline')

 def test_two_individuals_have_independent_five_second_holds(self):
  v=GuardianView()
  def data(t,a,b):return dict(schema=3,supported=True,expected_per_lane=2,columns=['team','lane','entity','hp','max'],updates=[dict(second=t,rows=[[2,1,102,b,4000],[2,1,101,a,4000]])])
  self.assertFalse(v.sample(data(1,4000,4000),1,1,'a'))
  rows=v.sample(data(2,3000,4000),2,2,'a');self.assertEqual([(x['entity'],x['ordinal']) for x in rows],[(101,1)])
  rows=v.sample(data(3,3000,2000),3,3,'a');self.assertEqual({x['entity'] for x in rows},{101,102})
  self.assertEqual([x['entity'] for x in v.sample(data(4,3000,2000),4,7,'a')],[102])
  self.assertFalse(v.sample(data(5,3000,2000),5,8,'a'))
  rows=v.sample(data(6,3000,1000),6,9,'a');self.assertEqual(rows[0]['ordinal'],2)
  self.assertFalse(v.sample(data(7,3000,0),7,10,'a'),'destroyed individual hidden')
 def test_late_lower_entity_id_does_not_renumber_existing_guardian(self):
  v=GuardianView()
  def data(t,rows):return dict(schema=3,supported=True,expected_per_lane=2,columns=['team','lane','entity','hp','max'],updates=[dict(second=t,rows=rows)])
  v.sample(data(1,[[2,1,102,4000,4000]]),1,1,'a')
  r=v.sample(data(2,[[2,1,102,3000,4000]]),2,2,'a');self.assertEqual(r[0]['ordinal'],1)
  r=v.sample(data(3,[[2,1,101,4000,4000],[2,1,102,2000,4000]]),3,3,'a');self.assertEqual(r[0]['entity'],102);self.assertEqual(r[0]['ordinal'],1)
 def test_compaction_and_maximum_five_columns(self):
  from PIL import Image,ImageFont
  from base_guardian_hud import draw_guardian_rows
  font=lambda n:ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'engine/fonts/NotoSansJP-Bold.ttf'),n)
  for team in (2,3):
   for count in range(4):
    rows=[dict(team=team,lane=1,entity=i,ordinal=i+1,fraction=.5) for i in range(2)]
    im=Image.new('RGBA',(2560,116));draw_guardian_rows(im,rows,font,origin_y=0,columns={(team,0):count})
    for column in (count,count+1):
     x=16+228*column if team==2 else 2560-16-220-228*column
     self.assertEqual(im.getpixel((x+3,0))[3],255)
    im=Image.new('RGBA',(2560,116));draw_guardian_rows(im,rows[1:],font,origin_y=0,columns={(team,0):count})
    x=16+228*count if team==2 else 2560-16-220-228*count
    self.assertEqual(im.getpixel((x+3,0))[3],255,'second individual closes the first column gap')
 def test_invalid_old_partial_or_changed_maximum(self):
  v=GuardianView();v.sample(self.data(1),1,1,'a')
  invalid=[dict(schema=1,supported=True,expected_per_team=6,updates=[]),self.data(2,-1),self.data(2,100,0),self.data(2,9000),self.data(2,float('nan'))]
  d=self.data(2);d['updates'][0]['rows'].append(d['updates'][0]['rows'][0]);invalid.append(d)
  d=self.data(2);d['updates'][0]['rows'][0][1]=0;invalid.append(d)
  for d in invalid:self.assertEqual(v.sample(d,2,2,'a'),[])
  self.assertEqual(v.sample(self.data(2,1000,4000),2,2,'a'),[],'denominator change resets');self.assertEqual(v.sample(self.data(2),5,3,'a'),[],'stale hidden')
 def test_lane_isolation_missingpair_andzero(self):
  v=GuardianView();d=self.data(1);d['updates'][0]['rows'].append([2,4,102,8000,8000]);v.sample(d,1,1,'a')
  d=self.data(2,4000);d['updates'][0]['rows'].append([2,4,102,8000,8000]);self.assertEqual([r['lane'] for r in v.sample(d,2,2,'a')],[1])
  d=self.data(3,4000);d['updates'][0]['rows'].append([2,4,102,2000,8000]);self.assertEqual([r['lane'] for r in v.sample(d,3,3,'a')],[1,4])
  d=self.data(4,0);self.assertEqual(v.sample(d,4,4,'a'),[],'destroyed lanehidden andmissinglane cleared')
  d=self.data(5,0);d['updates'][0]['rows'].append([2,4,102,1000,8000]);self.assertEqual(v.sample(d,5,5,'a'),[],'returning lane startsbaseline')
 def test_render_six_independent_lane_frames(self):
  from PIL import Image,ImageFont
  from base_guardian_hud import draw_guardian_rows
  root=Path(__file__).resolve().parents[1]/'engine';font=lambda n:ImageFont.truetype(str(root/'fonts/NotoSansJP-Bold.ttf'),n)
  im=Image.new('RGBA',(1920,1080));rows=[dict(team=t,lane=l,fraction=.5) for t in [2,3] for l in [1,4,6]];draw_guardian_rows(im,rows,font)
  for t,x in [(2,16),(3,1684)]:
   for y in [292,332,372]:
    self.assertEqual(im.getpixel((x+3,y))[3],255);self.assertEqual(im.getpixel((x+3,y+33))[3],255);self.assertEqual(im.getpixel((x,y+34))[3],0)
  self.assertLess(font(14).getlength('ベースガーディアン 100%'),176)
 def test_missing_lanes_keep_map_slots(self):
  from PIL import Image,ImageFont
  from base_guardian_hud import draw_guardian_rows
  font=lambda n:ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'engine/fonts/NotoSansJP-Bold.ttf'),n)
  for team,x in [(2,16),(3,1684)]:
   for lane,slot in [(1,0),(4,1),(6,2),(3,2)]:
    im=Image.new('RGBA',(1920,116));draw_guardian_rows(im,[dict(team=team,lane=lane,fraction=.5)],font,origin_y=0)
    self.assertEqual(im.getpixel((x+3,40*slot))[3],255)
    for other in set([0,1,2])-{slot}:self.assertEqual(im.getpixel((x,40*other))[3],0)
 def test_ambiguous_old_right_lane_is_not_overdrawn(self):
  from PIL import Image
  from base_guardian_hud import draw_guardian_rows
  im=Image.new('RGBA',(1920,116));draw_guardian_rows(im,[dict(team=2,lane=l,fraction=.5) for l in [3,6]],lambda n:None,origin_y=0)
  self.assertIsNone(im.getbbox())
 def test_small_hp_plane_has_three_rows_and_hides_in_details(self):
  import effect_bridge as b
  from PIL import Image
  from unittest.mock import patch
  import io,time
  rows=[dict(team=2,lane=lane,fraction=.5) for lane in [1,4,6]]
  state=b.State();state.last_http=state.native_at=time.monotonic();state.last_clock=100;state.tower_grid.update(dict(schema=2,columns=5,clock='1:40',bars=[]),time.monotonic());state.roster=[dict(detail=False) for _ in range(12)]
  with patch.object(b,'S',state),patch.object(b,'REPLAY',None),patch.object(b,'LIVE',None),patch.object(state.guardian_view,'sample',return_value=rows) as sample:
   im=Image.open(io.BytesIO(b.guardian_image(1920)));self.assertEqual(im.size,(1920,116));self.assertEqual(im.getpixel((19,113))[3],255);self.assertEqual(state.guardian_rows,rows)
   state.roster[0]['detail']=True;sample.reset_mock();im=Image.open(io.BytesIO(b.guardian_image(1920)));self.assertIsNone(im.getbbox());sample.assert_not_called();self.assertEqual(state.guardian_rows,[])
   state.roster[0]['detail']=False;state.native_at=0;im=Image.open(io.BytesIO(b.guardian_image(1920)));self.assertIsNone(im.getbbox())
   state.native_at=time.monotonic();state.last_http=0;im=Image.open(io.BytesIO(b.guardian_image(1920)));self.assertIsNone(im.getbbox())
 def test_fast_frame_stays_original_size_without_guardian_sampling(self):
  import effect_bridge as b
  from PIL import Image
  from unittest.mock import patch
  import io
  heroes=sorted(set(b.CAT['heroes'].values()),key=int)[:12];players=[dict(hero=str(h),pos=dict(x=i*140,y=54),width=140,detail=False) for i,h in enumerate(heroes)]
  with patch.object(b,'S',b.State()),patch.object(b,'REPLAY',None),patch.object(b,'LIVE',None),patch.object(b,'render_base_guardians',side_effect=AssertionError('HP belongs to the low-frequency plane')):
   im=Image.open(io.BytesIO(b.render(dict(time='0:01',players=players,width=1920))));self.assertEqual(im.size,(1920,420))
   for row in players:row['detail']=True
   im=Image.open(io.BytesIO(b.render(dict(time='0:01',players=players,width=1920))));self.assertEqual(im.size,(1920,900))
class UnifiedTowerTests(unittest.TestCase):
 def test_native_layout_bridge_and_stale_or_seek_rejection(self):
  from base_guardian_hud import TowerGrid
  g=TowerGrid();bar=lambda kind:dict(group='tower',kind=kind,team='team_friendly_container',slot=1)
  data=dict(schema=2,columns=5,clock='10:00',bars=[bar('guardian'),bar('walker')])
  self.assertTrue(g.update(data,10));self.assertEqual(g.columns(600,10),{(2,1):2});self.assertIsNone(g.columns(600,12));self.assertIsNone(g.columns(610,11))
  self.assertFalse(g.update(dict(data,bars=[bar('walker')]*2),11));self.assertFalse(g.update(dict(data,clock='x'),11));self.assertFalse(g.update(dict(data,columns=1),11));g.clear();self.assertIsNone(g.columns(600,11))
 def test_base_column_after_zero_one_two_native_kinds_for_both_teams(self):
  from PIL import Image,ImageFont
  from base_guardian_hud import draw_guardian_rows
  font=lambda n:ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'engine/fonts/NotoSansJP-Bold.ttf'),n)
  for width in [1280,1920,2560]:
   scale=min(1,width/1920)
   for team in [2,3]:
    for count in [0,1,2]:
     im=Image.new('RGBA',(width,116));draw_guardian_rows(im,[dict(team=team,lane=4,fraction=.5)],font,origin_y=0,columns={(team,1):count})
     x=16+round(228*scale*count) if team==2 else width-16-round(220*scale)-round(228*scale*count)
     self.assertEqual(im.getpixel((x+3,round(40*scale)))[3],255)
     if count:self.assertEqual(im.getpixel((16 if team==2 else width-17,round(40*scale)))[3],0)
 def test_state_layout_receipt_cleared_on_reset(self):
  import effect_bridge as b
  from unittest.mock import patch
  s=b.State();s.line('[SpecTowerLayout] {"schema":2,"columns":5,"clock":"0:10","bars":[]}')
  self.assertEqual(s.tower_grid.columns(10,__import__('time').monotonic()),{})
  with patch.object(b,'REPLAY',None),patch.object(b,'LIVE',None):s.reset()
  self.assertIsNone(s.tower_grid.columns(10,__import__('time').monotonic()))


class BuildingCaptionTests(unittest.TestCase):
 def test_caption_visible_ink_center_and_edge_without_clipping(self):
  from base_guardian_hud import _building_caption
  font=str(Path(__file__).resolve().parents[1]/'engine/fonts/NotoSansJP-Bold.ttf')
  for scale in [2/3,1]:
   for text in ['ガーディアン 1%','ウォーカー 100%','ベースガーディアン 100%','シュライン 50%','パトロン 99%','弱体化パトロン 100%']:
    im=_building_caption(text,font,round(14*scale),round(176*scale),round(19*scale),(240,238,230,255),False,True);b=im.getchannel('A').point(lambda a:255 if a>=64 else 0).getbbox();self.assertIsNotNone(b);self.assertLessEqual(abs((b[0]+b[2])/2-im.width/2),1);self.assertLessEqual(abs((b[1]+b[3])/2-im.height/2),1);self.assertGreater(b[1],0);self.assertLess(b[3],im.height)
   for text in ['ヨーク','ブロードウェイ','グリニッジ','パープル']:
    im=_building_caption(text,font,round(10*scale),round(176*scale),round(12*scale),(210,208,199,255),False,False);b=im.getchannel('A').point(lambda a:255 if a>=64 else 0).getbbox();self.assertLessEqual(b[0],1);self.assertLessEqual(abs((b[1]+b[3])/2-im.height/2),1)
 def test_team_fill_uses_full_content_height_and_preserves_hp_width(self):
  from PIL import Image,ImageFont
  import base_guardian_hud as b
  from unittest.mock import patch
  font=lambda n:ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'engine/fonts/NotoSansJP-Bold.ttf'),n)
  for width in [1280,1920,2560]:
   scale=min(1,width/1920);w=round(220*scale);h=round(34*scale);content=round(40*scale);available=w-round(44*scale)
   for team in [2,3]:
    color=(212,134,11,204) if team==2 else (77,117,195,204)
    expected=Image.alpha_composite(Image.new('RGBA',(1,1),(16,19,13,238)),Image.new('RGBA',(1,1),color)).getpixel((0,0))
    for fraction in [.01,.25,.5,1]:
     im=Image.new('RGBA',(width,116));x=16 if team==2 else width-16-w;fill=round(available*fraction)
     with patch.object(b,'_building_caption',side_effect=lambda text,path,size,cw,ch,*args:Image.new('RGBA',(cw,ch))):
      b.draw_guardian_rows(im,[dict(team=team,lane=1,fraction=fraction)],font,origin_y=0)
     for y in range(1,h-1):
      self.assertEqual(im.getpixel((x+content,y)),expected,'full-height team fill must cover the lane and title area')
      self.assertEqual(im.getpixel((x+content+fill-1,y)),expected,'remaining HP width')
      self.assertEqual(im.getpixel((x+content+fill,y)),(16,19,13,238),'empty HP stays dark')
     self.assertEqual(im.getpixel((x+content,0)),(75,73,63,255),'top border preserved')
     self.assertEqual(im.getpixel((x+content,h-1)),(75,73,63,255),'bottom border preserved')
     self.assertEqual(im.getpixel((x+8,h//2)),(16,19,13,238),'icon area stays separate')
 def test_base_percent_rounds_half_up_like_native(self):
  from PIL import Image,ImageFont
  import base_guardian_hud as b
  from unittest.mock import patch
  font=lambda n:ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'engine/fonts/NotoSansJP-Bold.ttf'),n)
  for fraction,label in [(.325,'33%'),(.125,'13%'),(.995,'100%')]:
   with patch.object(b,'_building_caption',wraps=b._building_caption) as caption:
    b.draw_guardian_rows(Image.new('RGBA',(1920,116)),[dict(team=2,lane=1,fraction=fraction)],font,origin_y=0)
    self.assertTrue(caption.call_args_list[1].args[0].endswith(label));self.assertEqual(caption.call_args_list[1].args[2],14);self.assertEqual(caption.call_args_list[0].args[2],10)

if __name__=='__main__':unittest.main()

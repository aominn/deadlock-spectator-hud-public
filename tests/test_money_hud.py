from pathlib import Path
import sys,unittest,types
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from money_hud import MoneyTimeline,compact,native_matches,money_records,glyph_png
class MoneyTests(unittest.TestCase):
 def data(self):return dict(schema=1,columns=['hero','team','total','wallet'],supported=True,updates=[dict(second=10,rows=[[i+1,2 if i<6 else 3,4000,800] for i in range(12)]),dict(second=11,rows=[[i+1,2 if i<6 else 3,4000,0] for i in range(12)])])
 def test_purchase_seek_unknown_and_zero(self):
  t=MoneyTimeline(self.data(),range(1,13));self.assertEqual(t.at(11,list(range(1,13)))[0]['wallet'],0);self.assertEqual(t.at(10,list(range(1,13)))[0]['wallet'],800)
  for clock,heroes in [(9,list(range(1,13))),(13,list(range(1,13))),(10,[1]*12),(10,list(range(1,12)))]:self.assertEqual(t.at(clock,heroes),[])
  self.assertEqual(compact(4000)+'/'+compact(800),'4k/800');self.assertEqual(compact(0),'0')
 def test_malformed_and_team(self):
  for change in ['duplicate','negative','bool','overspend','team']:
   d=self.data();v=d['updates'][0]['rows'][0]
   if change=='duplicate':v[0]=2
   if change=='negative':v[3]=-1
   if change=='bool':v[3]=True
   if change=='overspend':v[3]=5000
   if change=='team':v[1]=3
   with self.assertRaises(ValueError):MoneyTimeline(d,{i+1:2 if i<6 else 3 for i in range(12)})
  self.assertEqual(MoneyTimeline(None,range(1,13)).at(10,list(range(1,13))),[])
 def test_native_total_crosscheck(self):
  self.assertTrue(native_matches('4k',4000));self.assertTrue(native_matches('16.8k',16812));self.assertFalse(native_matches('—',0));self.assertFalse(native_matches('4k',7000))
 def test_render_all12_and_native_fallback(self):
  from PIL import Image,ImageFont
  font=ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'engine/fonts/NotoSansJP-Bold.ttf'),13);players=[dict(hero=i+1,pos=dict(x=i*140,y=54),width=140,money=dict(total='4k',rect=[i*140+50,150,40,22],dead=False)) for i in range(12)];rows=MoneyTimeline(self.data(),range(1,13)).at(10,list(range(1,13)));im=Image.new('RGBA',(1920,420));self.assertEqual(len(money_records(rows,players,1920)),12);players[0]['money']['total']='4.6k';out=money_records(rows,players,1920);self.assertEqual(out[0]['text'],'4.6k/800');players[0]['money']['total']='—';self.assertEqual(len(money_records(rows,players,1920)),11);self.assertEqual(money_records([],players,1920),[]);players[1]['money']['rect'][0]=-9999;self.assertEqual(len(money_records(rows,players,1920)),10)
 def test_replay_and_live_source_binding(self):
  from replay_effect_source import ReplayEffectSource
  from live_effect_source import LiveEffectSource
  roster=[dict(hero=i+1,handle=100+i,team=2 if i<6 else 3) for i in range(12)];index=dict(schema=2,success=True,match='124289809',source_sha256='a'*64,roster=roster,events=[],money=self.data());source=ReplayEffectSource(index);heroes=list(range(1,13));self.assertEqual(source.money_at(10,heroes),[]);source.observe_log("[Demo] playing demo from 'replays/124289809.dem'");self.assertEqual(len(source.money_at(10,heroes)),12);source.observe_log('[Client] Disconnecting from server:');self.assertEqual(source.money_at(10,heroes),[])
  live=LiveEffectSource();snapshot=dict(roster=roster,money=self.data());self.assertEqual(live.money_at(snapshot,10,heroes),[]);live.bound=True;self.assertEqual(len(live.money_at(snapshot,10,heroes)),12);live.reset();self.assertEqual(live.money_at(snapshot,10,heroes),[])
 def test_native_left_label_and_wallet_are_independent(self):
  players=[dict(hero=i+1,pos=dict(x=i*140,y=54),width=140,money=dict(total='4.6k',rect=[i*140+50,150,40,20],dead=False)) for i in range(12)]
  rows=MoneyTimeline(self.data(),range(1,13)).at(10,list(range(1,13)))
  values=money_records(rows,players,1920);self.assertEqual(len(values),12);self.assertEqual(values[0]['text'],'4.6k/800');self.assertEqual(values[0]['total'],4000)
  frozen=money_records(rows,players,1920,frozen=True);self.assertEqual(frozen[0]['text'],'4k/800');self.assertEqual(frozen[0]['native_total'],'4.6k')
  players[0]['money']='invalid';self.assertEqual(len(money_records(rows,players,1920)),11)
  players[0]['money']=dict(total='—',rect=[50,150,40,20],dead=False);self.assertEqual(len(money_records(rows,players,1920)),11)
  self.assertEqual(money_records(rows[:11],players,1920),[])
 def test_glyphs_are_transparent_and_use_local_font(self):
  from unittest.mock import patch
  from PIL import Image
  import io,os
  from money_hud import game_fonts
  game=os.environ.get('SPEC_TEST_GAME')
  if not game:self.skipTest('Optional installed-game font check')
  with patch.dict(os.environ,{'SPEC_HUD_GAME':game}):bold,regular=game_fonts()
  image=Image.open(io.BytesIO(glyph_png(4000,800,bold,regular)));self.assertEqual(image.size,(78,20));self.assertEqual(image.getpixel((0,0))[3],0);self.assertIsNotNone(image.getbbox())
  with patch.dict(os.environ,{'SPEC_HUD_GAME':'missing-game'}):
   with self.assertRaises(ValueError):game_fonts()
 def test_confirmed_receipt_survives_rounded_wallet_guard(self):
  import effect_bridge as b
  from unittest.mock import patch
  st=b.State();st.last_clock=1258;st.last_http=100;st.native_at=100
  st.roster=[dict(hero=i+1,pos=dict(x=i*140,y=54),width=140,money=dict(total='4k',rect=[i*140+50,150,40,20],dead=False)) for i in range(12)]
  st.money_rows=[dict(hero=i+1,team=2 if i<6 else 3,total=4000,wallet=800) for i in range(12)];st.roster[0]['money']['total']='4.6k'
  st.economy_view.push([dict(hero=1,cause='urn',delta=165,id='test')],100)
  q=dict(clock=['20:58'],hero=['1'],total=['4.6k'])
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:100),patch.object(b,'game_fonts',lambda:('bold','regular')),patch.object(b,'economy_glyph_png',lambda cause,value,font:('receipt',cause,value)),patch.object(b,'glyph_png',lambda *args,**kw:('money',args[1],kw['native_total'])):
   self.assertEqual(b.money_image(q),('money',800,'4.6k')) # receipts never replace the base money image
   with self.assertRaises(ValueError):b.money_image({**q,'total':['4k']})
   st.economy_view.clear()
   self.assertEqual(b.money_image(q),('money',800,'4.6k'))
   with self.assertRaises(ValueError):b.money_image({**q,'total':['4k']})
 def test_endpoint_rejects_stale_wrong_owner_and_total(self):
  import effect_bridge as b
  from unittest.mock import patch
  st=b.State();st.last_clock=54;st.last_heartbeat='0:54';st.last_http=100;st.native_at=100
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:100):
   for q in [dict(clock=['0:53'],hero=['1'],total=['4k']),dict(clock=['0:54'],hero=['99'],total=['4k'])]:
    with self.assertRaises(ValueError):b.money_image(q)
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:104):
   with self.assertRaises(ValueError):b.money_image(dict(clock=['0:54'],hero=['1'],total=['4k']))
if __name__=='__main__':unittest.main()

class IdentityExtrasTests(unittest.TestCase):
 def fixture(self):
  d=MoneyTests().data();d['kda_updates']=[dict(second=10,rows=[[i+1,2 if i<6 else 3,i,2,3] for i in range(12)])];d['sales']=dict(schema=1,supported=True,generation=0,events=[dict(id='0-1',sequence=1,generation=0,seconds=10,hero=1,team=2,ability=2829638276,verified_sell=True)]);return d
 def test_optional_identity_and_sales(self):
  t=MoneyTimeline(self.fixture(),{i+1:2 if i<6 else 3 for i in range(12)});v=t.at(10,list(range(1,13)));self.assertEqual(v[0]['kda'],[0,2,3]);self.assertEqual(len(v[0]['sales']),1);self.assertEqual(v[1]['kda'],[1,2,3]);self.assertIsNotNone(t._identity_cache);self.assertEqual(t.at(11,list(range(1,13)))[0]['kda'],[0,2,3])
 def test_invalid_extra_never_corrupts_money(self):
  d=self.fixture();d['kda_updates'][0]['rows'][0][2]=-1;d['sales']['events'][0]['verified_sell']=False;v=MoneyTimeline(d,range(1,13)).at(10,list(range(1,13)))[0];self.assertNotIn('kda',v);self.assertNotIn('sales',v);self.assertEqual(v['wallet'],800)
 def test_sale_render_baseline_expiry_and_occupied_slots(self):
  import effect_bridge as b
  from PIL import Image
  from unittest.mock import patch
  st=b.State();st.native_at=10;st.stable_after=0;st.roster=[dict(hero=1,pos=dict(x=0,y=54),width=140,scale=1,cards=[],notice_top=156)];st.money_rows=[dict(hero=1,kda=[1,2,3])]
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:10):
   self.assertEqual(b.render_identity_notices(Image.new('RGBA',(1920,900)),10)[0]['text'],'K 1  D 2  A 3')
   st.roster[0]['detail']=True
   self.assertTrue(any(x['kind']=='kda' for x in b.render_identity_notices(Image.new('RGBA',(1920,900)),10)))
   self.assertEqual(st.kda_hold['1'],[1,2,3])
   st.roster[0]['detail']=False
   self.assertEqual(b.render_identity_notices(Image.new('RGBA',(1920,900)),10)[0]['rect'],[10,24,120,16])
  st.native_at=11;st.money_rows[0]['sales']=[dict(id='new',ability=2829638276,hero=1)]
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:11):
   rows=b.render_identity_notices(Image.new('RGBA',(1920,900)),11);sale=[x for x in rows if x['kind']=='sale'];self.assertEqual(sale[0]['rect'],[0,210,140,32]);self.assertEqual(sale[0]['name'],'エクストラリジェネ')
   st.roster[0]['cards']=[[0,210,140,32],[0,246,140,32]];self.assertFalse(any(x['kind']=='sale' for x in b.render_identity_notices(Image.new('RGBA',(1920,900)),11)))
  st.native_at=16;st.money_rows[0].pop('sales');st.roster[0]['cards']=[]
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:16):self.assertFalse(any(x['kind']=='sale' for x in b.render_identity_notices(Image.new('RGBA',(1920,900)),16)))

 def test_kda_font_smooth_and_cached(self):
  import effect_bridge as b
  from unittest.mock import patch
  from pathlib import Path
  fallback=str(Path(b.ROOT)/'fonts/NotoSansJP-Bold.ttf')
  b.kda_texture.cache_clear()
  with patch.object(b,'game_fonts',return_value=(fallback,fallback)) as native:
   im=b.kda_texture((12,3,18));self.assertEqual(im.size,(120,16));self.assertEqual(im.mode,'RGBA');self.assertIs(b.kda_texture((12,3,18)),im);native.assert_called_once();self.assertIsNotNone(im.getbbox());self.assertTrue(any(0<a<255 for a in im.getchannel('A').tobytes()))
  b.kda_texture.cache_clear()
  with patch.object(b,'game_fonts',side_effect=ValueError('unavailable')):self.assertIsNotNone(b.kda_texture((1,2,3)).getbbox())

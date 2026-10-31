from pathlib import Path
import unittest,sys,io
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
class StableMoneyLayout(unittest.TestCase):
 def roster(self,width=1920):
  result=[]
  for i in range(12):
   x=(width-1812)/2+(-42+i*140 if i<6 else 972+42+(i-6)*140)
   result.append({'hero':i+1,'pos':{'x':x,'y':46},'width':140,'cards':[[x+3,230,134,58]],'money':{'total':'4k','rect':[x+31,142,78,20],'dead':False}})
  return result
 def hit(self,a,z):return a[0]<z[0]+z[2] and z[0]<a[0]+a[2] and a[1]<z[1]+z[3] and z[1]<a[1]+a[3]
 def test_twelve_receipt_rows_clear_all_fixed_information(self):
  for width in (1920,2560):
   players=self.roster(width);boxes=[]
   for p in players:
    rect=b.economy_geometry(p,width);x,y,w,h=rect;self.assertEqual((y,w,h),(120,78,20));center=p['pos']['x']+70
    self.assertFalse(self.hit(rect,p['money']['rect']));self.assertFalse(self.hit(rect,(center-10,171,20,20)))
    for box in p['cards']+boxes:self.assertFalse(self.hit(rect,box))
    boxes.append(rect)
 def test_receipts_draw_without_replacing_or_requiring_wallet(self):
  st=b.State();st.last_http=100;st.native_at=100;st.last_clock=600;st.roster=self.roster();st.economy_view.push([{'hero':1,'id':'one','cause':'kill','delta':674}],100)
  font=str(Path(b.ROOT)/'fonts/NotoSansJP-Bold.ttf');image=Image.new('RGBA',(1920,420))
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:100.2),patch.object(b,'game_fonts',lambda:(font,font)):
   rows=b.render_economy(image,b.card_obstacles(st.roster,1920));self.assertEqual(rows[0]['amount'],674);self.assertEqual(rows[0]['presentation'],'independent-receipt-lane')
   self.assertIsNotNone(image.getbbox());self.assertEqual(image.crop((43,142,121,162)).getbbox(),None,'normal money area remains transparent')
   self.assertEqual(st.roster[0]['money']['total'],'4k')
   with self.assertRaises(ValueError):b.money_image({'clock':['10:00'],'hero':['1'],'total':['4k']})
   st.money_rows=[{'hero':i+1,'team':2 if i<6 else 3,'total':4000,'wallet':800} for i in range(12)]
   with patch.object(b,'glyph_png',lambda *args,**kwargs:'normal money'):
    self.assertEqual(b.money_image({'clock':['10:00'],'hero':['1'],'total':['4k']}),'normal money')
 def test_all_positive_causes_share_amount_only_and_center(self):
  from economy_hud import economy_glyph_png,CAUSES
  font=str(Path(b.ROOT)/'fonts/NotoSansJP-Bold.ttf');expected=economy_glyph_png('kill',674,font)
  for cause,sign in CAUSES.items():
   if sign>0:self.assertEqual(economy_glyph_png(cause,674,font),expected)
  image=Image.open(io.BytesIO(expected));box=image.getbbox();self.assertLessEqual(abs((box[0]+box[2])/2-39),2)
  self.assertNotEqual(economy_glyph_png('loss',-674,font),expected)
 def test_native_bag_rechecks_owner_time_amount_and_dedup(self):
  st=b.State();st.roster=self.roster();st.last_clock=600;st.last_http=100;st.native_at=100
  data={'id':'bag-1','hero':'1','clock':600,'amount':355,'cause':'soul-bag-pickup','source':'native-killer-gold-label','personal_income_verified':True}
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:100):
   for bad in [dict(data,hero='99'),dict(data,clock=590),dict(data,amount=-355),dict(data,id='bad'),dict(data,source='guessed')]:b.accept_bag(bad)
   self.assertEqual(st.economy_view.active,{})
   b.accept_bag(data);b.accept_bag(data);self.assertEqual(st.economy_view.at(1,100)['amount'],355)
   st.reset();self.assertEqual(st.economy_view.active,{});self.assertEqual(st.economy_view.pending,{})
if __name__=='__main__':unittest.main()

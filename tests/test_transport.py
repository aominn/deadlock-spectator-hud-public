from pathlib import Path
import sys,unittest,threading,http.client
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
class TransportTests(unittest.TestCase):
 def test_png_keepalive_and_bounded_rejection(self):
  server=b.ThreadingHTTPServer(('127.0.0.1',0),b.H);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
  before=dict(b.S.metrics)
  try:
   with patch.object(b,'money_image',return_value=b'PNG-test') as image:
    for _ in range(3):
     client.request('GET','/money.png?token='+b.TOKEN);response=client.getresponse();self.assertEqual(response.status,200);self.assertEqual(response.read(),b'PNG-test')
    self.assertEqual(image.call_count,3)
   self.assertEqual(b.S.metrics['transport_connections']-before.get('transport_connections',0),1)
   self.assertEqual(b.S.metrics['transport_money_requests']-before.get('transport_money_requests',0),3)
   self.assertEqual(b.S.metrics['transport_money_ok']-before.get('transport_money_ok',0),3)
   with patch.object(b,'money_image',side_effect=ValueError('stale')):
    client.request('GET','/money.png?token='+b.TOKEN);response=client.getresponse();self.assertEqual(response.status,400);response.read();self.assertTrue(response.will_close);client.close()
   self.assertEqual(b.S.metrics['transport_rejected']-before.get('transport_rejected',0),1)
  finally:client.close();server.shutdown();server.server_close();thread.join(3)
 def test_unknown_token_on_fresh_connection(self):
  # Authentication rejection is independent of the preceding 400/connection-close path.
  server=b.ThreadingHTTPServer(('127.0.0.1',0),b.H);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
  try:
   client.request('GET','/money.png?token=wrong');response=client.getresponse();self.assertEqual(response.status,404);response.read();self.assertTrue(response.will_close)
  finally:client.close();server.shutdown();server.server_close();thread.join(3)
if __name__=='__main__':unittest.main()

from pathlib import Path
import sys,unittest,tempfile,json
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import service
class StatusTests(unittest.TestCase):
 def test_busy_diagnostic_does_not_abort_next_status(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d);self.assertTrue(service.write_status(home,{'state':'waiting'}))
   with patch.object(service,'save',side_effect=PermissionError('file busy')):
    self.assertFalse(service.write_status(home,{'state':'watching'}))
   self.assertEqual(json.loads((home/'service.json').read_text())['state'],'waiting')
   self.assertTrue(service.write_status(home,{'state':'watching'}));self.assertEqual(json.loads((home/'service.json').read_text())['state'],'watching')
 def test_unrelated_failures_are_not_hidden(self):
  with patch.object(service,'save',side_effect=ValueError('bad data')):
   with self.assertRaises(ValueError):service.write_status(Path('.'),{})

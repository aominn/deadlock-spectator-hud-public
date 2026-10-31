"""One startup transaction. No persistent verification cache or game-side changes."""
from pathlib import Path
import time
from manager_core import discover,save
from asset_install import adopt_bundle

def startup(manager):
 timings={}
 def phase(name,operation):
  start=time.monotonic();result=operation();timings[name]=round(time.monotonic()-start,3);return result
 update=phase('release',lambda:adopt_bundle(manager))
 if update.get('updated'):return {**update,'timings':timings}
 phase('stop',manager.stop_service)
 config=manager.config()
 # This migration only removes our own obsolete Run registration.
 if config.get('startup_cleanup')!=1:
  phase('legacy_cleanup',lambda:manager.autostart(False))
  config=manager.config();config['startup_cleanup']=1;save(manager.config_file,config)
 game=config.get('game','')
 if not game or not (Path(game)/'gameinfo.gi').is_file():
  games=phase('discover',discover)['games'];game=games[0] if games else ''
 if config.get('enabled'):phase('service',manager.start_service)
 return {'updated':False,'game':game,'timings':timings}

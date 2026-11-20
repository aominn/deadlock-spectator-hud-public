import assert from 'node:assert/strict';
import { attachMidbossTimer } from '../parser/midboss-timer.mjs';

for (const basis of ['replay', 'broadcast']) {
 const fields = {
  m_flGameStartTime: 80,
  m_nTotalPausedTicks: 0,
  m_bGamePaused: false,
  m_eGameState: 7,
  m_tNextMidBossSpawnTime: 0,
 };
 const rule = { getField: key => fields[key.split('.').at(-1)] };
 const demo = { getEntitiesByClassName: () => [rule] };
 let deliver;
 const parser = {
  getDemo: () => demo,
  registerPostInterceptor: (_, callback) => { deliver = callback; },
 };
 const timer = attachMidbossTimer(parser, { basis });
 const visit = t => deliver({ tick: Math.round((t + (basis === 'broadcast' ? 80 : 0)) * 64) });
 visit(basis === 'broadcast' ? 2000 : 0);
 fields.m_tNextMidBossSpawnTime = 2556.75;
 visit(2136.78125);
 visit(2298);
 assert.deepEqual(timer.snapshot().updates, [[basis === 'broadcast' ? 2000 : 0, 0], [2137, 2556.75]]);
 fields.m_eGameState = 11;
 visit(2438);
 assert.deepEqual(timer.snapshot().updates.at(-1), [2438, 0]);
 fields.m_eGameState = 7;
 fields.m_tNextMidBossSpawnTime = 0;
 visit(1300);
 assert.deepEqual(timer.snapshot().updates, [[1300, 0]], 'discard the previous timeline on a clock rollback');
}
console.log('PASS native replay/live Mid Boss deadline, transition rounding, end and rollback');

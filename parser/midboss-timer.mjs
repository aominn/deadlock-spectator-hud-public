import { InterceptorStage } from 'deadem';
import { moneyClock } from './money-parser.mjs';

// The game-rules deadline already uses elapsed match seconds, like the HUD clock.
export function attachMidbossTimer(parser, { basis = 'replay', maxUpdates = 256 } = {}) {
 const demo = parser.getDemo();
 const updates = [];
 let previous = -1;
 let gameStart;
 let overflow = false;

 parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET, packet => {
  const rules = demo.getEntitiesByClassName('CCitadelGameRulesProxy');
  const rule = rules.length === 1 && rules[0].active !== false ? rules[0] : null;
  const elapsed = moneyClock(packet.tick, rule, basis);
  if (!Number.isFinite(elapsed) || elapsed < 0) return;

  const second = Math.ceil(elapsed);
  const start = rule.getField('m_pGameRules.m_flGameStartTime');
  if (second < previous || start !== gameStart) {
   updates.length = 0;
   overflow = false;
  }
  previous = second;
  gameStart = start;

  const state = rule.getField('m_pGameRules.m_eGameState');
  const next = rule.getField('m_pGameRules.m_tNextMidBossSpawnTime');
  const deadline = [7, 8].includes(state) && Number.isFinite(next) && next > elapsed
   && next - elapsed <= 3600 ? next : 0;
  if (overflow || updates.at(-1)?.[1] === deadline) return;
  if (updates.at(-1)?.[0] === second) updates.pop();
  updates.push([second, deadline]);

  if (updates.length > maxUpdates) {
   if (basis === 'broadcast') updates.shift();
   else {
    overflow = true;
    updates.length = 0;
   }
  }
 });

 return {
  snapshot() {
   return { schema: 1, updates: updates.slice() };
  },
 };
}

import {InterceptorStage} from 'deadem';
import {moneyClock} from './money-parser.mjs';

export function spectatorRows(demo) {
  const rows = demo.getEntitiesByClassName('CCitadelPlayerController')
    .filter(player => player.active)
    .map(player => ['m_nHeroID', 'm_iTeamNum', 'm_iHeroDamage', 'm_iGoldNetWorth', 'm_unLobbyPlayerSlot']
      .map(field => player.getField(field)))
    .filter(([hero, team]) => hero > 0 && (team === 2 || team === 3));
  if (rows.length !== 12 || rows.filter(row => row[1] === 2).length !== 6 ||
      new Set(rows.map(row => row[0])).size !== 12 || new Set(rows.map(row => row[4])).size !== 12 ||
      rows.some(row => !row.every(Number.isInteger) || row[2] < 0 || row[2] > 1e7 ||
        row[3] < 0 || row[3] > 1e7 || row[4] < 0 || row[4] > 23)) return [];
  return rows.sort((a, b) => a[4] - b[4]).map(row => row.slice(0, 4));
}

export function attachSpectatorStats(parser, {basis = 'replay'} = {}) {
  const live = basis === 'broadcast';
  const demo = parser.getDemo();
  const updates = [];
  let last = -1;
  parser.registerPostInterceptor(InterceptorStage.DEMO_PACKET, packet => {
    const rules = demo.getEntitiesByClassName('CCitadelGameRulesProxy');
    if (rules.length !== 1) return;
    const state = rules[0].getField('m_pGameRules.m_eGameState');
    const second = Math.floor(moneyClock(packet.tick, rules[0], basis));
    if (!Number.isInteger(second) || second < 0 || second > 21600 || second === last) return;
    if (second < last) updates.length = 0;
    last = second;
    const rows = state === 7 || state === 8 || live && state === 11 ? spectatorRows(demo) : [];
    if (rows.length) updates.push({second, rows});
    if (live && updates.length > 90) updates.shift();
  });
  return {snapshot: () => ({schema: 1, updates: updates.slice()})};
}

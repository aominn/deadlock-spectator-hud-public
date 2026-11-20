import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../mod-src/spectator_probe.js', import.meta.url), 'utf8');
function functionsBetween(first, last) {
    return source.slice(source.indexOf(first), source.indexOf(last, source.indexOf(first)));
}
const hud = vm.createContext({});
vm.runInContext(
    functionsBetween('function specViewport(', '(function(){') +
    functionsBetween('function objectiveGeometry(', 'function layoutObjectives(') +
    functionsBetween('function positionName(', 'function nameOwnerReady(') +
    functionsBetween('function updateRosterTeams(', 'function scanPlayers(') +
    functionsBetween('function layout(){\n var timer=', 'function tick(){\n if(!ctx.IsValid())'),
    hud
);

function panel(x, y, width, height, scale) {
    return {
        GetPositionWithinWindow: () => ({x, y}),
        actuallayoutwidth: width,
        actuallayoutheight: height,
        actualuiscale_x: scale,
    };
}

const near = (actual, expected, tolerance = 0.001) =>
    assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} vs ${expected}`);

// Match the same raw coordinate convention seen in the game, without assuming
// the minimap's own scale equals the HUD host's scale.
const replays = [
    {size: [1280, 720], scale: 2 / 3, map: [1007, 442, 252, 252], badge: [25, 55, 59, 67]},
    {size: [1920, 1080], scale: 1, map: [1511, 663, 378, 378], badge: [38, 82, 88, 100]},
    {size: [2560, 1440], scale: 4 / 3, map: [2015, 884, 504, 504], badge: [51, 109, 117, 133]},
    {size: [3840, 2160], scale: 2, map: [3022, 1327, 756, 756], badge: [76, 164, 176, 200]},
];
for (const {size, scale, map: mapBox, badge: badgeBox} of replays) {
    const [width, height] = size;
    // Ensure calculations subtract the host origin consistently.
    const [ox, oy] = [-300, 120];
    const root = panel(ox, oy, width, height, scale);
    const map = panel(ox + mapBox[0], oy + mapBox[1], mapBox[2], mapBox[3], 1.05 * scale);
    const badge = panel(ox + badgeBox[0], oy + badgeBox[1], badgeBox[2], badgeBox[3], scale);
    const player = panel(ox + 12 * scale, oy + 82 * scale, 140 * scale, 238 * scale, scale);
    player.FindChildTraverse = () => badge;
    const view = hud.specViewport(root);
    near(view.width, 1920);
    near(view.height, 1080);
    near(hud.specPanelBox(map, view).width, 378);
    near(hud.specPanelBox(badge, view).width, 88, 1);
    const name = hud.positionName(player, root, {actuallayoutwidth: 120 * scale}, -26, 120);
    near(name.center, (badgeBox[0] + badgeBox[2] / 2) / scale);
    near(name.x + name.width / 2, name.center);
    near(name.y, 56);
    const objective = hud.objectiveGeometry(map, root);
    near(objective.x + objective.width, 1892);
    near(objective.y, mapBox[1] / scale - 72);

    const timer = {visible: true, _specBounds: objective};
    root.FindChildTraverse = () => timer;
    Object.assign(hud, {parent: root, panels: [{style: {}}, {style: {}}]});
    assert.ok(hud.layout());
    const [statsX, statsY] = hud.panels[0].style.position.split(' ').map(parseFloat);
    assert.ok(statsY + 278 <= objective.y - 12);
    near(statsX + 480, objective.x + objective.width, 1);

    timer.visible = false;
    assert.ok(hud.layout(), 'hidden timer reserves the same statistics position');
    near(parseFloat(hud.panels[0].style.position), statsX);
    timer._specBounds = null;
    assert.ok(hud.layout(), 'statistics also work without measured timer geometry');
    assert.ok(parseFloat(hud.panels[0].style.position) + 480 <= view.width - 28);
}

for (const [width, scale] of [[960, 1], [1280, 1], [1728, 1], [1920, 2/3], [1920, 2], [2560, 1]]) {
    const root = panel(0, 0, width * scale, 1080 * scale, scale);
    const headers = [0, 1].map(() => ({style: {}, _icon: {style: {}}, _name: {style: {}}}));
    const bans = [0, 1].map(() => ({style: {}, _loaded: true}));
    Object.assign(hud, {
        ctx: {
            GetParent: () => root,
            FindChildTraverse: id => panel((id === 'TeamFriendly' ? 12 : width * .56) * scale, 82 * scale, width * .43 * scale, 1000 * scale, scale),
            SetHasClass: () => {},
        },
        rosterOptions: {teamName: true, teamIcon: true},
        teamHeaders: headers, teamBans: bans,
        teamHeader: side => headers[side], teamBanPanel: (_, side) => bans[side],
        updateSeriesHeader: () => {}, showTeamHeading: () => {}, find: () => null,
    });
    hud.updateRosterTeams(true);
    assert.ok([...headers, ...bans].every(node => node.visible));
    const left = node => parseFloat(node.style.position);
    const right = node => left(node) + parseFloat(node.style.width);
    assert.ok(left(bans[0]) >= 12 && right(bans[0]) < left(headers[0]));
    assert.ok(right(headers[0]) <= width / 2 - 116 + .01);
    assert.ok(left(headers[1]) >= width / 2 + 116 && right(headers[1]) < left(bans[1]));
    assert.ok(right(bans[1]) <= width - 12 + .01);
}
console.log('PASS render-pixel geometry, replay-scale roster/portrait, objective timers, timer-independent stats and contained team headings');

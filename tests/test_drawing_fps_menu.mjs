import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const script = readFileSync(new URL('../mod-src/drawing_fps_menu.js', import.meta.url), 'utf8');

test('drawing FPS commands are explicit and limited to the open hideout or spectator menu', () => {
    for (const language of ['japanese', 'en-US']) {
        const actions = [];
        const scheduled = [];
        let spectator = false;
        let hideout = false;
        let practice = false;
        let open = false;
        const labelTitle = {};
        const tools = { visible: false, FindChildTraverse: () => labelTitle };
        const labels = [{}, {}];
        const commandLabels = [{}, {}];
        const options = labels.map((label, index) => ({
            visible: true,
            FindChildTraverse: id => id.endsWith('Command') ? commandLabels[index] : label,
            SetPanelEvent: (event, callback) => {
                assert.equal(event, 'onactivate');
                actions.push(callback);
            }
        }));
        const gameState = {
            GetParent: () => null,
            BHasClass: name => (name === 'connectedToHideout' && hideout) ||
                (name === 'connectedToHeroTesting' && practice)
        };
        const hud = {
            GetParent: () => gameState,
            BHasClass: name => name === 'spec_mode' && spectator
        };
        const menu = {
            IsValid: () => true,
            GetParent: () => hud,
            BHasClass: name => name === 'ShowEscapeMenu' && open,
            FindChildTraverse: id => ({
                SpecEscapeTools: tools,
                SpecDrawingFpsEnable: options[0],
                SpecDrawingFpsReset: options[1],
                SpecReplayBarToggle: { SetPanelEvent() {}, FindChildTraverse: () => ({}) }
            })[id]
        };
        const commands = [];
        vm.runInNewContext(script, { $: {
            GetContextPanel: () => menu,
            Language: () => language,
            DispatchEvent: (event, command) => {
                assert.equal(event, 'CitadelConCommand');
                commands.push(command);
            },
            Schedule: (_, callback) => scheduled.push(callback)
        }});

        assert.deepEqual(options.map(option => option.visible), [false, false]);
        assert.equal(tools.visible, false);
        open = true;
        scheduled.shift()();
        assert.equal(tools.visible, true);
        assert.equal(labelTitle.text, language === 'japanese' ? '観戦HUD' : 'Spectator HUD');
        actions.forEach(click => click());
        assert.deepEqual(commands, []);

        spectator = true;
        open = false;
        scheduled.shift()();
        assert.deepEqual(options.map(option => option.visible), [true, true]);
        actions.forEach(click => click());
        assert.deepEqual(commands, []);

        open = true;
        const expected = language === 'japanese'
            ? ['描き込み中のFPS低下を抑える', '標準に戻す']
            : ['Reduce drawing FPS drops', 'Restore default'];
        assert.deepEqual(labels.map(label => label.text), expected);
        actions.forEach(click => click());
        assert.deepEqual(commands, ['engine_no_focus_sleep 0', 'engine_no_focus_sleep 20']);
        assert.deepEqual(commandLabels.map(label => label.text), commands);

        spectator = false;
        hideout = true;
        practice = true;
        scheduled.shift()();
        assert.deepEqual(options.map(option => option.visible), [true, true]);
        assert.equal(commands.length, 2);
        actions.forEach(click => click());
        assert.deepEqual(commands.slice(2), ['engine_no_focus_sleep 0', 'engine_no_focus_sleep 20']);

        hideout = false;
        scheduled.shift()();
        assert.deepEqual(options.map(option => option.visible), [false, false]);
        actions.forEach(click => click());
        assert.equal(commands.length, 4);

        practice = false;
        scheduled.shift()();
        assert.deepEqual(options.map(option => option.visible), [false, false]);
        actions.forEach(click => click());
        assert.equal(commands.length, 4);
    }
});

test('the Esc menu keeps the replay controls and lower HUD layout in sync', () => {
    const css = readFileSync(new URL('../mod-src/toast-override.css', import.meta.url), 'utf8');
    assert.match(css, /\.spec_mode #PlaybackControls\.SpecReplayBarHidden \{ visibility: collapse; \}/);
    const compactRule = css.split('/* Remove the native replay spacing')[1];
    const [selectors, declarations] = compactRule.split('*/')[1].trim().split('{');
    const targets = ['AbilitiesContainer', 'StatsAndModsContainer', 'hudActivePlayerStats'];
    assert.deepEqual(selectors.split(',').map(selector => selector.trim().split(' #').at(-1)), targets.concat(targets));
    assert.match(declarations, /^\s*margin-bottom: 0px;\s*\}/);
    for (const language of ['japanese', 'en-US']) {
        let replay = false;
        let open = true;
        let withScrubber = true;
        let menuValid = true;
        let groupsPresent = true;
        const scheduled = [];
        const label = {};
        const tools = { visible: false, FindChildTraverse: () => ({}) };
        let click;
        const toggle = {
            visible: false,
            SetPanelEvent: (_, callback) => { click = callback; },
            FindChildTraverse: () => label
        };
        const fpsOption = {
            SetPanelEvent() {},
            FindChildTraverse: () => ({})
        };
        const topBar = { style: { visibility: 'visible' } };
        const root = {
            GetParent: () => null,
            BHasClass: name => name === 'replay_playback' && replay,
            FindChildTraverse: id => ({ PlaybackControls: activeBar, TopBar: topBar })[id]
        };
        const hud = { GetParent: () => root, BHasClass: name => name === 'spec_mode', FindChildTraverse: () => null };
        const layout = {
            GetParent: () => hud,
            FindChildTraverse: id => groupsPresent && targets.includes(id) ? {} : null,
            classes: new Set(),
            AddClass(name) { this.classes.add(name); },
            RemoveClass(name) { this.classes.delete(name); },
            IsValid: () => true
        };
        let activeBar = replayBar();
        const menu = {
            IsValid: () => menuValid,
            GetParent: () => hud,
            BHasClass: name => name === 'ShowEscapeMenu' && open,
            FindChildTraverse: id => ({
                SpecEscapeTools: tools,
                SpecReplayBarToggle: toggle
            })[id] ?? fpsOption
        };
        function replayBar(visibility = '') {
            return {
                style: { visibility },
                classes: new Set(),
                AddClass(name) { this.classes.add(name); },
                RemoveClass(name) { this.classes.delete(name); },
                valid: true,
                IsValid() { return this.valid; },
                GetParent: () => layout,
                FindChildTraverse: id => id === 'ReplayScrubber' && withScrubber ? {} : null
            };
        }
        function tick() { scheduled.shift()(); }
        function isHidden(bar = activeBar) { return bar.classes.has('SpecReplayBarHidden'); }
        function isCompact() { return layout.classes.has('SpecReplayCompactLayout'); }

        vm.runInNewContext(script, { $: {
            GetContextPanel: () => menu,
            Language: () => language,
            DispatchEvent: () => assert.fail('seek bar must not dispatch console commands'),
            Schedule: (_, callback) => scheduled.push(callback)
        }});
        const [hide, show] = language === 'japanese'
            ? ['シークバーを隠す', 'シークバーを表示']
            : ['Hide replay bar', 'Show replay bar'];

        assert.equal(toggle.visible, false);
        click();
        assert.equal(isHidden(), false);

        replay = true;
        withScrubber = false;
        tick();
        assert.equal(toggle.visible, false);
        click();
        assert.equal(isHidden(), false);

        withScrubber = true;
        tick();
        assert.equal(toggle.visible, true);
        assert.equal(label.text, hide);
        click();
        assert.equal(isHidden(), true);
        assert.equal(isCompact(), true);
        assert.equal(topBar.style.visibility, 'visible');
        assert.equal(label.text, show);

        open = false;
        tick();
        assert.equal(toggle.visible, false);
        click();
        assert.equal(isHidden(), true);
        assert.equal(isCompact(), true);
        open = true;
        tick();
        assert.equal(label.text, show);
        click();
        assert.equal(isHidden(), false);
        assert.equal(isCompact(), false);
        assert.equal(label.text, hide);

        click();
        replay = false;
        tick();
        assert.equal(isHidden(), false);
        assert.equal(isCompact(), false);
        assert.equal(toggle.visible, false);

        replay = true;
        const previousBar = activeBar;
        click();
        activeBar = replayBar('visible');
        open = false;
        tick();
        assert.equal(isHidden(previousBar), false);
        assert.equal(isHidden(), false);
        assert.equal(isCompact(), false);
        open = true;
        click();
        assert.equal(isHidden(), true);
        assert.equal(isCompact(), true);
        activeBar.valid = false;
        tick();
        assert.equal(isCompact(), false);
        assert.equal(toggle.visible, false);
        activeBar = replayBar('visible');
        groupsPresent = false;
        click();
        assert.equal(isHidden(), true);
        assert.equal(isCompact(), false);
        click();
        groupsPresent = true;
        click();
        assert.equal(isCompact(), true);
        menuValid = false;
        tick();
        assert.equal(isHidden(), false);
        assert.equal(activeBar.style.visibility, 'visible');
        assert.equal(isCompact(), false);
        assert.equal(scheduled.length, 0);
    }
});

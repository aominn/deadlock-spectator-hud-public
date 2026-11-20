(function () {
    'use strict';
    var menu = $.GetContextPanel();
    var hud = menu.GetParent();
    var tools = menu.FindChildTraverse('SpecEscapeTools');
    var enable = menu.FindChildTraverse('SpecDrawingFpsEnable');
    var reset = menu.FindChildTraverse('SpecDrawingFpsReset');
    var replayToggle = menu.FindChildTraverse('SpecReplayBarToggle');
    if (!hud || !tools || !enable || !reset || !replayToggle) return;
    var replayLabel = replayToggle.FindChildTraverse('SpecReplayBarToggleLabel');
    var hiddenBar = null;
    var compactLayout = null;

    var language = typeof $.Language === 'function' ? String($.Language()).toLowerCase() : '';
    var japanese = /^(ja($|[-_])|japanese$)/.test(language) ||
        (!language && $.Localize('#upgrade_close_range') === 'クローズクォーター');
    tools.FindChildTraverse('SpecEscapeToolsTitle').text = japanese ? '観戦HUD' : 'Spectator HUD';
    enable.FindChildTraverse('SpecDrawingFpsEnableLabel').text =
        japanese ? '描き込み中のFPS低下を抑える' : 'Reduce drawing FPS drops';
    reset.FindChildTraverse('SpecDrawingFpsResetLabel').text =
        japanese ? '標準に戻す' : 'Restore default';
    var enableCommand = 'engine_no_focus_sleep 0';
    var resetCommand = 'engine_no_focus_sleep 20';
    enable.FindChildTraverse('SpecDrawingFpsEnableCommand').text = enableCommand;
    reset.FindChildTraverse('SpecDrawingFpsResetCommand').text = resetCommand;

    function fpsOptionsAvailable() {
        for (var panel = hud; panel; panel = panel.GetParent()) {
            if (panel.BHasClass('spec_mode') || panel.BHasClass('connectedToHideout')) return true;
        }
        return false;
    }

    function escapeMenuOpen() {
        for (var panel = menu; panel; panel = panel.GetParent()) {
            if (panel.BHasClass('ShowEscapeMenu')) return true;
        }
        return false;
    }

    function activate(command) {
        if (fpsOptionsAvailable() && escapeMenuOpen()) $.DispatchEvent('CitadelConCommand', command);
    }

    enable.SetPanelEvent('onactivate', function () { activate(enableCommand); });
    reset.SetPanelEvent('onactivate', function () { activate(resetCommand); });

    function findPlaybackBar() {
        var root = hud;
        while (root.GetParent()) root = root.GetParent();
        var bar = root.FindChildTraverse('PlaybackControls');
        return bar && bar.IsValid() && bar.FindChildTraverse('ReplayScrubber') ? bar : null;
    }

    function inReplay() {
        for (var panel = hud; panel; panel = panel.GetParent()) {
            if (panel.BHasClass('replay_playback')) return true;
        }
        return false;
    }

    function findCompactLayout(bar) {
        for (var panel = bar.GetParent(); panel; panel = panel.GetParent()) {
            if (panel.FindChildTraverse('AbilitiesContainer') &&
                panel.FindChildTraverse('StatsAndModsContainer') &&
                panel.FindChildTraverse('hudActivePlayerStats')) return panel;
        }
        return null;
    }

    function restoreReplayBar() {
        if (hiddenBar && hiddenBar.IsValid()) hiddenBar.RemoveClass('SpecReplayBarHidden');
        if (compactLayout && compactLayout.IsValid()) compactLayout.RemoveClass('SpecReplayCompactLayout');
        hiddenBar = null;
        compactLayout = null;
    }

    function updateReplayToggle() {
        var replay = inReplay();
        var open = replay && escapeMenuOpen();
        var bar = replay && (open || hiddenBar) ? findPlaybackBar() : null;
        if (hiddenBar && (hiddenBar !== bar || !hiddenBar.IsValid() ||
            (compactLayout && !compactLayout.IsValid()))) restoreReplayBar();
        var showToggle = open && !!bar;
        if (replayToggle.visible !== showToggle) replayToggle.visible = showToggle;
        if (!showToggle) return;
        var title = hiddenBar === bar
            ? (japanese ? 'シークバーを表示' : 'Show replay bar')
            : (japanese ? 'シークバーを隠す' : 'Hide replay bar');
        if (replayLabel.text !== title) replayLabel.text = title;
    }

    replayToggle.SetPanelEvent('onactivate', function () {
        if (!inReplay() || !escapeMenuOpen()) return;
        var bar = findPlaybackBar();
        if (!bar) return;
        if (bar === hiddenBar) {
            restoreReplayBar();
        } else {
            restoreReplayBar();
            bar.AddClass('SpecReplayBarHidden');
            hiddenBar = bar;
            compactLayout = findCompactLayout(bar);
            if (compactLayout) compactLayout.AddClass('SpecReplayCompactLayout');
        }
        updateReplayToggle();
    });

    function updateVisibility() {
        if (!menu.IsValid()) {
            restoreReplayBar();
            return;
        }
        var visible = fpsOptionsAvailable();
        if (enable.visible !== visible) enable.visible = visible;
        if (reset.visible !== visible) reset.visible = visible;
        updateReplayToggle();
        var open = escapeMenuOpen();
        if (tools.visible !== open) tools.visible = open;
        $.Schedule(0.25, updateVisibility);
    }
    updateVisibility();
})();

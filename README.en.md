# Deadlock Spectator HUD

Source preparation snapshot **0.5.12 / Windows 10–11 x64**. An unofficial HUD for spectating and replays. It is not developed, approved or supported by Valve.

[日本語](README.md)

> This repository is being prepared for distribution. No runnable Release ZIP has been published here yet. The setup instructions below apply once a release is available.

## Setup

1. Download `DeadlockSpectatorHUD-0.5.12-win-x64.zip` from [Releases](https://github.com/aominn/deadlock-spectator-hud-public/releases) and extract the entire ZIP. Use the runnable release, not the source-code ZIP.
2. Close Deadlock and open `HudManager.exe` in the extracted folder.
3. Select `Steam/steamapps/common/Deadlock/game/citadel`, then choose **Set up**. Images are prepared from your installed game.
4. Choose **Enable HUD**, then **Launch game**. Enter a spectator match or a supported replay.

Steam and Deadlock are required. Python, Node.js and .NET do not need separate installation.
Keep the manager open while using the HUD. It continues when minimized; closing it stops the companion and analysis. To restore the normal HUD, close the game and choose **Restore normal mode**.

## Language

The manager and drawing toolbar follow the Windows display language: Japanese uses Japanese; every other language uses English. Regional number/date formatting does not determine the UI language.

Additional game text follows the Deadlock client language: Japanese uses Japanese; every other language uses English. The original game's UI language is left unchanged. For example, an English Windows installation with Japanese Deadlock has an English manager and Japanese HUD additions.

Items resolve through exact localized aliases tied to internal names and IDs. Ability icons use hero ID and slot. Ambiguous or unknown names are not guessed. Complete coverage of every game language, hero, effect or future update is not guaranteed.

## Update and recovery

Close the game and manager, extract the latest release to a new folder, then open its `HudManager.exe`. A newer release carries over your settings and preserves the previous version. Opening an older or identical release does not automatically downgrade.

**Help** provides **Verify files**, **Refresh images**, and **Restore previous version**. Close the game before these operations. Missing images use a retained image of the same identity, or stay hidden if none is available. Other features continue.


If a game update changes native UI resources, a compatible HUD release is required; refreshing images alone may not resolve it. See [game update checks](docs/GAME-UPDATES.txt).

## Features

- Hero names, K/D/A, total souls / wallet, and confirmed individual soul changes.
- Purchases, sales, ability upgrades and verified ultimate unlocks.
- Effect icons shown for three seconds when applied. Four align normally; additional effects overlap and fade.
- Urn holder, up to two bridge buffs, and individual Rejuvenator ownership.
- Team soul lead, Rejuvenator count, Mid Boss HP/timer, bridge timer and native-position rifts.
- Lane-based building damage bars held for five seconds; two base guardians shown individually; shrines side by side.
- Three-column inventory in the detailed view.

Enable “Draw lines (spectating/replays only)” in the manager to use F8. Enable it again each time you reopen the manager. F8 toggles the drawing toolbar. Choose **Watch**, or press Esc, to use game controls while retaining drawings; choose **Draw** to resume. Drawing covers the screen, including the minimap.

## Limits and materials

Testing on a moved local folder is distinct from testing on a physical second PC. All OBS capture methods, exclusive fullscreen, every live feature and long replay seeks have not been exhaustively verified. See [current status](docs/STATUS.txt) and [English instructions](docs/INSTALL.en.txt).

The release does not bundle game images, original game UI resources or game fonts. They are prepared on the user's PC. This does not imply Valve approval or permission to redistribute game materials. Game and material rights belong to their respective owners.


[Changelog](docs/CHANGELOG.txt) / [Build](docs/BUILD.txt) / [Portable checks](docs/PORTABLE.txt) / [Licenses](licenses)

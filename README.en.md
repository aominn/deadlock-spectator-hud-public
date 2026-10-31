# Deadlock Spectator HUD

An unofficial HUD for **spectating and replays** in Deadlock. Follow purchases, ability upgrades, status effects and the economy, then draw on the screen to explain a play. Designed for watching matches, tournament broadcasts and post-match analysis.

[日本語](README.md) · Windows 10/11 x64

**[Download the runnable 0.6.0 ZIP](https://github.com/aominn/deadlock-spectator-hud-public/releases/tag/v0.6.0)** and extract everything. Code → Download ZIP is the development source, not the runnable package.

![Actual 0.6.0 replay with economy, KDA, effect notifications and lane-grouped building HP](docs/images/spectator-overview-0.6.0.jpg)

*Photos show HUD 0.6.0 with game build 6839 in Japanese. Full views are cropped; close-ups combine enlarged regions with external numbered labels. Game values and icons have not been altered.*

## What it adds to the standard view

### Purchases and ability changes

**Icon-and-name notifications** appear below each hero for purchases, sales and ability upgrades. Item accents distinguish Weapon, Vitality and Spirit. Upgrades show ◇1–3; confirmed unlocks use the game's unlock icon. Explain how a purchase changes the next fight without losing track of the player.

![Close-ups of an unlock and purchase, followed by a tier-one upgrade](docs/images/purchase-upgrade-0.6.0.jpg)

*1: unlock. 2: purchase. 3: upgrade. These are separate regions of the same actual frame.*

### Economy and carried buffs

Each hero shows a name, K/D/A and **total souls / wallet**. Confirmed individual soul changes appear over the economy area. The central team lead appears only for the leading side after the first five minutes.

![1 hero name, KDA and total/wallet; 2 team economy lead](docs/images/economy-0.6.0.jpg)

The HUD also marks the Urn carrier, up to two Bridge Buffs with a white remaining-time outline, individual Rejuvenator eligibility and the team's remaining count. Rejuvenator ownership is visible in the photos.

### Status application icons

Supported stuns, slows, silence, curse, transformations, invulnerability and other supported effects appear as **icons without text labels** near the affected hero. A new application is shown for about three seconds. Up to four appear separately; five or more overlap. These brief notifications are not effect-duration timers.

![Enlarged hero row showing status icons and Rejuvenator ownership below the economy display](docs/images/effects-ownership-0.6.0.jpg)

*Transient application notifications and carried-buff indicators are separate systems. Coverage is not guaranteed for every hero or effect.*

### Buildings and objectives

- Damaged Guardian, Walker and Base Guardian HP is grouped **by lane**, retained for about five seconds after the last hit. Simultaneous entries pack horizontally. The two Base Guardians are separate entries.
- Shrines use two horizontal columns; Patron displays follow its phase. Mid Boss has a dedicated HP display.
- Bridge Buff countdowns and Mid Boss time information sit above the minimap. An unavailable state may show “—”, as in the photo.
- The detailed view arranges inventory in three columns while retaining the top hero information and map timers.

![1 Walker; 2 same-lane Base Guardian; 3 opposing Walker; 4 map timers](docs/images/objectives-0.6.0.jpg)

*The numbered panels are different regions of one frame. This is not a permanent list of every building.*

## First setup

Requires Windows with Steam and Deadlock installed. The runnable ZIP includes its runtime; no separate Python, Node.js or .NET installation is needed.

1. Download the runnable ZIP from [Release](https://github.com/aominn/deadlock-spectator-hud-public/releases/tag/v0.6.0) and **extract all files**. Do not run from inside the ZIP.
2. Exit Deadlock and open **HudManager.exe** from the extracted folder.
3. Select **Deadlock/game/citadel**, then **Prepare**. Images are prepared from the game installed on that PC.
4. Choose **Enable HUD → Launch game**, then open spectating or a compatible replay.

![Actual 0.6.0 manager showing folder selection, preparation, enable, restore and launch controls in Japanese](docs/images/manager-0.6.0.jpg)

Keep the manager open while spectating. Minimizing keeps it running; **closing with × stops its helper processes**. Allow preparation time when joining late or analyzing a replay for the first time.

## Draw on the screen

Enable **Draw lines (spectating/replays only)** in the manager and press **F8** in the game, or the key you selected.

![Actual pen strokes drawn over both the replay screen and minimap](docs/images/drawing-0.6.0.jpg)

- Choose four colors, thin/thick strokes and pen/arrow tools. Undo and Clear are available on the toolbar.
- **Watch or Esc** returns to game controls while keeping the lines; **Draw** resumes drawing. F8 toggles toolbar visibility.
- Draw anywhere, including over the minimap. Lines are fixed to screen coordinates and do not follow the camera.
- Lines survive switching to another window. Seeking, changing matches, restoring normal mode or exiting the tool clears them.
- Enable the drawing checkbox each time you open the manager. Drawing can reduce FPS.

[Drawing details](docs/DRAWING.txt)

## Restore normal mode and update

**Restore**: Exit Deadlock, then select **Restore normal mode** in the manager.

**Update**: Close the game and manager, extract the latest ZIP into a new folder, and open its HudManager.exe. No manual individual-file replacement is needed.

**Troubleshooting**: After exiting the game, **Troubleshooting** provides file checks, image refresh and rollback to a retained previous version. [Installation and recovery](docs/INSTALL.txt)

## Languages and verification scope

The manager and drawing toolbar follow the **Windows display language**. Additional in-game text follows the **Deadlock language**. Each uses Japanese for Japanese and English otherwise. The photos here are Japanese.

On November 1, 2026, three recent replays were downloaded and confirmed to start with 0.6.0. Photos come from two of them. Seeking into the middle of one replay terminated the game, so the long-seek limitation remains.

A user has confirmed basic installation, asset preparation, spectating/replays, normal restoration, Japanese/English and × shutdown on another PC. Exhaustive testing of all heroes/effects, all live features, OBS capture methods and exclusive fullscreen is incomplete. [Current limitations](docs/STATUS.txt)

Report problems through [GitHub Issues](https://github.com/aominn/deadlock-spectator-hud-public/issues) with HUD version, game language, spectating/replay and reproduction steps. Do not post authentication data in logs. A [contact form](https://aominn.jp/form/) is also available.

## Unofficial tool and licenses

Not developed, approved or supported by Valve. Intended for spectating and replays, not regular gameplay.

Game icons, native UI originals, game fonts and a generated MOD are not included in the runnable ZIP. They are prepared from the user's installed game. Documentation photos are illustrations; game-content rights remain with their respective owners.

Authored code uses [MIT](LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.txt) and [photo provenance](docs/images/README.txt) for other components and documentation images.

[Changelog](docs/CHANGELOG.txt) · [Build](docs/BUILD.txt) · [Distribution checks](docs/PORTABLE.txt) · [Local assets](docs/LOCAL-ASSETS.txt)

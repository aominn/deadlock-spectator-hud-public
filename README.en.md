# Deadlock Spectator HUD

An unofficial HUD for **spectating and replays** in Deadlock. Follow purchases, ability upgrades, status effects and the economy, then draw on the screen to explain a play. Designed for watching matches, tournament broadcasts and post-match analysis.

[日本語](README.md) · Windows 10/11 x64

This combines a MOD that changes the in-game display with a companion manager. **Use it for spectating and replays. Before regular play, exit the game and select Restore normal mode.** It is not developed or approved by Valve.

[Setup](#first-setup) · [Restore and update](#restore-normal-mode-and-update) · [Coverage](docs/STATUS.txt)

**[Download the runnable 0.6.0 ZIP](https://github.com/aominn/deadlock-spectator-hud-public/releases/tag/v0.6.0)** and extract everything. Code → Download ZIP is the development source, not the runnable package.

![Actual 0.6.0 replay with economy, KDA, effect notifications and lane-grouped building HP](docs/images/spectator-overview-0.6.0.jpg)

*These are actual game and manager screenshots, shown in Japanese. Close-ups preserve portrait or location context. See [photo provenance](docs/images/README.txt).*

## HUD changes

### Purchases and ability changes

**Icon-and-name notifications** appear below each hero for purchases, detected sales and ability upgrades. Not every sale is guaranteed to be reported. Item accents distinguish Weapon, Vitality and Spirit. Upgrades show ◇1–3; confirmed unlocks use the game's unlock icon. Explain how a purchase changes the next fight without losing track of the player.

Notifications appear **below the corresponding hero portrait**.

**Item purchase**

![Yamato's portrait with a purchase notification directly below it](docs/images/notification-purchase-context-0.6.0.jpg)

**Ability upgrade**

![Deadman Danny's portrait with an upgrade notification directly below it](docs/images/notification-upgrade-context-0.6.0.jpg)

**Ability unlock**

![Rat King's portrait with an unlock notification directly below it](docs/images/notification-unlock-context-0.6.0.jpg)

### Total souls and wallet

Each hero shows a name, K/D/A and **total souls / wallet**. For example, “4.1k / 909” means about 4,100 total souls and 909 in the wallet. Confirmed individual soul changes appear over this area. Both team totals appear below the match clock at the top center. After five minutes, the percentage lead appears beside the clock on the leading team's side, calculated relative to the opposing team's total.

![Timer-centered view with hero total/wallet values on both sides and team economy](docs/images/economy-centered-0.6.0.jpg)

### Compare inventories in the detailed view

Open the **scoreboard/detailed view using your configured game key** to see each hero's inventory in **three columns**. Compare builds during a quieter moment after a fight. Top hero information and timers above the minimap remain visible.

<img src="docs/images/detail-inventory-context-clean.jpg" width="410" alt="McGinnis, Vindicta and Abrams with three-column inventories directly below their portraits">

### Status application notifications

Supported stuns, slows, silence, curse, transformations, invulnerability and other supported effects appear as **icons without names beside the hero portrait**. The photo shows three notifications beside Violet.

<img src="docs/images/status-three-context-0.6.0.jpg" width="280" alt="Three real effect notifications beside Violet's portrait">

A new application is shown for about three seconds. Up to four appear separately; five or more overlap. These are not effect-duration timers; only effects supported by the HUD are shown.

### Urn and Bridge Buff ownership

Separate from brief effect notifications, the HUD marks the Urn carrier above the hero portrait and up to two Bridge Buffs beside the ultimate icon below the economy area. A white outline around each Bridge Buff shows its remaining duration. In the Silver photo, the two icons on the left are the Bridge Buffs.

| Urn carrier | Two Bridge Buffs |
| :---: | :---: |
| <img src="docs/images/urn-carrier-0.6.0.jpg" width="220" alt="Warden carrying the Urn"> | <img src="docs/images/bridge-buffs-two-0.6.0.jpg" width="220" alt="Silver holding two Bridge Buffs"> |

### Rejuvenator eligibility

A **yellow icon below a hero's economy area** marks that hero's remaining Rejuvenator eligibility. The team's remaining count appears **below the match clock at the top center**, with an icon and a value such as “×3”. Individual eligibility and team remaining uses are different information: the count is not the number of heroes holding the buff. In this photo, “×3” belongs to the team on the right.

![Match clock at 26:25 centered between the teams, with x3 below it and yellow eligibility icons below the right-side heroes](docs/images/rejuvenator-three-clock-centered.jpg)

### Lane-grouped building HP

Damaged Guardian, Walker and Base Guardian HP appears **on the left and right of the screen below the hero row**, retained for about five seconds after the last hit. Simultaneous entries **in the same lane** pack horizontally. The two Base Guardians have separate HP entries. This is not a permanent list of every building.

![A Walker and two Base Guardians in the same lane, displayed in one horizontal group](docs/images/lane-building-hp-0.6.0.jpg)

The two Shrines are shown side by side; Patron displays follow its phase. Mid Boss has a dedicated HP display.

### Timers above the minimap

Bridge Buff counts down to its **next scheduled appearance**. Mid Boss shows a respawn countdown or a spawned state when available from the game; an unavailable state shows “—”. The remaining duration of a collected Bridge Buff is shown by its white outline in the hero row.

<img src="docs/images/map-timers-0.6.0.jpg" width="410" alt="Minimap with Bridge Buff and Mid Boss time information directly above it">

## First setup

**Use with other MODs has not been tested. Display or functional problems caused by MOD conflicts are outside the scope of support.**

Requires Windows 10/11 x64, with Steam and Deadlock installed. The runnable ZIP includes its runtime; no separate Python, Node.js or .NET installation is needed.

1. Download **DeadlockSpectatorHUD-0.6.0-win-x64.zip** from [Release](https://github.com/aominn/deadlock-spectator-hud-public/releases/tag/v0.6.0) and **extract all files**. Do not run from inside the ZIP.
2. Exit Deadlock and open **HudManager.exe** from the extracted folder.
3. Select **Deadlock/game/citadel**, then **Set up**. Images are prepared from the game installed on that PC.
4. Choose **Enable HUD → Launch game**, then open spectating or a compatible replay.

![Actual 0.6.0 manager showing folder selection, preparation, enable, restore and launch controls in Japanese](docs/images/manager-0.6.0.jpg)

Older replays may be incompatible with the current game. Some long seeks can exit the game. Leave live spectating before opening a replay.

Keep the manager open while spectating. Minimizing keeps it running; **closing with × stops its helper processes**. Closing alone does not restore normal mode. Allow preparation time when joining late or analyzing a replay for the first time.

## Draw on the screen

Circle a location or draw an arrow to explain a movement: **draw directly on the spectator screen with the mouse**, including over the minimap.

Enable **Drawing (spectator / replay only)** in the manager and press **F8** in the game. You can change this key in the manager.

![A red circle, cyan and yellow strokes, thick white lines, a red arrow and the drawing toolbar over the game](docs/images/drawing-colored-example.jpg)

- Choose four colors, thin/thick strokes and pen/arrow tools. Undo and Clear are available on the toolbar.
- **Watch or Esc** returns to game controls while keeping the lines; **Draw** resumes drawing. F8 toggles toolbar visibility.
- Draw anywhere, including over the minimap. Lines are fixed to screen coordinates and do not follow the camera.
- Lines survive switching to another window. Seeking, changing matches, restoring normal mode or exiting the tool clears them.
- Enable the drawing checkbox each time you open the manager. Drawing can reduce FPS.

[Drawing details (Japanese)](docs/DRAWING.txt)

## Restore normal mode and update

**Before returning to regular play**: Exit Deadlock, then select **Restore normal mode** in the manager. To spectate with the HUD again, exit the game and choose **Enable HUD → Launch game**.

If a game update breaks the display, restore normal mode and wait for a compatible HUD release.

**Update**: Get the latest runnable ZIP through **Download latest** in the manager or [GitHub Releases](https://github.com/aominn/deadlock-spectator-hud-public/releases). Close the game and manager, extract everything into a new folder, and open its HudManager.exe. Follow the manager's prompts, enable the HUD and launch the game. No manual individual-file replacement is needed.

**Help**: After exiting the game, **Help** provides file checks, image refresh and rollback to a retained previous version. [Installation and recovery](docs/INSTALL.en.txt)

## Display languages

The manager and drawing toolbar follow the **Windows display language**. Additional in-game text follows the **Deadlock language**. Each uses Japanese for Japanese and English otherwise. The photos here are Japanese.

Report problems through [GitHub Issues](https://github.com/aominn/deadlock-spectator-hud-public/issues) with HUD version, game language, spectating/replay and reproduction steps. Do not post authentication data in logs. A [contact form](https://aominn.jp/form/) is also available.

## Unofficial tool and licenses

Not developed, approved or supported by Valve. Intended for spectating and replays, not regular gameplay.

Game icons, native UI originals, game fonts and a generated MOD are not included in the runnable ZIP. They are prepared from the user's installed game. Documentation photos are illustrations; game-content rights remain with their respective owners.

Authored code uses [MIT](LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.txt) and [photo provenance](docs/images/README.txt) for other components and documentation images.

[Changelog](docs/CHANGELOG.txt) · [Build](docs/BUILD.txt) · [Distribution checks](docs/PORTABLE.txt) · [Local assets](docs/LOCAL-ASSETS.txt)

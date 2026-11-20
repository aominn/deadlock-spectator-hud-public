"""Match statistics shown through the existing game HUD image transport."""
from bisect import bisect_right
from functools import lru_cache
import ctypes
import io
import json
import os
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont, ImageOps

COLORS = {2: '#edb548', 3: '#79b5ff'}
TEAM_NAMES = {
    2: ('ヒドゥン・キング', 'The Hidden King'),
    3: ('アークマザー', 'The Archmother'),
}


def team_name(team, ja):
    return TEAM_NAMES[team][0 if ja else 1]
MAX_SECOND = 21600


def read_updates(data, teams, limit):
    if not isinstance(data, dict) or data.get('schema') != 1:
        return {}
    updates = data.get('updates')
    if not isinstance(updates, list) or len(updates) > limit or len(teams) != 12:
        return {}
    result = {}
    previous = -1
    for sample in updates:
        if not isinstance(sample, dict):
            return {}
        second, rows = sample.get('second'), sample.get('rows')
        if type(second) is not int or not previous < second <= MAX_SECOND:
            return {}
        if not isinstance(rows, list) or len(rows) != 12:
            return {}
        if any(not isinstance(row, list) or len(row) != 4 or any(type(v) is not int for v in row)
               or teams.get(row[0]) != row[1] or row[1] not in COLORS
               or not all(0 <= v <= 10_000_000 for v in row[2:]) for row in rows):
            return {}
        if len({row[0] for row in rows}) != 12 or sum(row[1] == 2 for row in rows) != 6:
            return {}
        result[second] = tuple(map(tuple, rows))
        previous = second
    return result


def difference(rows):
    return sum(row[3] if row[1] == 2 else -row[3] for row in rows)


class StatsTimeline:
    def __init__(self, data, teams):
        self.samples = read_updates(data, teams, MAX_SECOND + 1)
        self.times = tuple(self.samples)
        self.differences = tuple((second, difference(rows)) for second, rows in self.samples.items())

    def at(self, clock):
        end = bisect_right(self.times, clock)
        rows = self.samples[self.times[end-1]] if end and clock-self.times[end-1] <= 1 else ()
        return rows, self.differences[:end]


class LiveStats:
    def __init__(self):
        self.route = None
        self.snapshot_key = None
        self.samples = {}
        self.history = {}

    def update(self, snapshot, route, clock, heroes):
        if route is None:
            return ()
        if route != self.route:
            self.__init__()
            self.route = route
        if not isinstance(snapshot, dict):
            return ()
        key = (snapshot.get('session'), snapshot.get('generation'), snapshot.get('updated_at'))
        if key != self.snapshot_key:
            teams = {p['hero']: p['team'] for p in snapshot['roster']}
            self.samples = read_updates(snapshot.get('spectator_stats'), teams, 90)
            self.snapshot_key = key
        if not 0 <= clock <= MAX_SECOND:
            return ()
        # Only store samples actually reached by the native spectator clock.
        # A gap during a disconnect remains a gap, even if the next fragment
        # includes some of those seconds.
        rows = self.samples.get(clock, ())
        if rows and {r[0] for r in rows} == set(heroes):
            self.history[clock] = difference(rows)
        else:
            rows = ()
        return rows

    def through(self, clock):
        return tuple((second, self.history[second]) for second in sorted(self.history) if second <= clock)


DEFAULT_STATS_KEYS = {'damage': (0x78, 0, 'F9'), 'graph': (0x79, 0, 'F10')}
KEY_CODES = (set(range(0x30, 0x3A)) | set(range(0x41, 0x5B)) |
             set(range(0x60, 0x6A)) | set(range(0x70, 0x88)) |
             set(range(0x20, 0x29)) | {0x2D, 0x2E, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
                                       0xC0, 0xDB, 0xDC, 0xDD, 0xDE, 0xE2}) - {0x7B}


def load_stats_keys(path):
    if path is None:
        return DEFAULT_STATS_KEYS
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        keys = {}
        for action in ('drawing', 'damage', 'graph'):
            row = saved[action]
            code, modifiers, display = row['code'], row['modifiers'], row['display']
            if (type(code) is not int or code not in KEY_CODES or type(modifiers) is not int
                    or not 0 <= modifiers <= 7 or (code == 0x73 and modifiers & 1)
                    or not isinstance(display, str) or not display.isascii() or not 1 <= len(display) <= 32):
                return DEFAULT_STATS_KEYS
            keys[action] = code, modifiers, display
        if len({value[:2] for value in keys.values()}) != 3:
            return DEFAULT_STATS_KEYS
        return {action: keys[action] for action in DEFAULT_STATS_KEYS}
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_STATS_KEYS


class StatsPanels:
    def __init__(self):
        self.open = None
        self.scope = None
        self.snapshot = None

    def poll(self, scope, events):
        if scope != self.scope:
            self.open = None
            self.scope = scope
            self.snapshot = None
        if scope is None:
            return
        for name in events:
            self.open = None if self.open == name else name
            self.snapshot = None



class WindowsStatsKeys:
    def __init__(self, bindings):
        from ctypes import wintypes as wt
        self.user = ctypes.WinDLL('user32')
        self.kernel = ctypes.WinDLL('kernel32')
        self.user.GetForegroundWindow.restype = wt.HWND
        self.user.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
        self.kernel.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
        self.kernel.OpenProcess.restype = wt.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = (wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD))
        self.kernel.CloseHandle.argtypes = (wt.HANDLE,)
        self.wt = wt

        self.ids = {}
        self.bindings = bindings
        self.attempted = False
        self.failed = []
        self.user.RegisterHotKey.argtypes = (wt.HWND, ctypes.c_int, wt.UINT, wt.UINT)
        self.user.UnregisterHotKey.argtypes = (wt.HWND, ctypes.c_int)
        self.user.PeekMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT)
        self.foreground = (None, 0, False)

    def events(self, active):
        active = active and self.game_foreground()
        if active and not self.attempted:
            self.attempted = True
            self.failed = []
            for identifier, (name, (vk, modifiers, display)) in enumerate(self.bindings.items(), 1):
                if self.user.RegisterHotKey(None, identifier, 0x4000 | modifiers, vk):
                    self.ids[identifier] = name
                else:
                    self.failed.append(display)
        message = self.wt.MSG()
        result = []
        while self.user.PeekMessageW(ctypes.byref(message), None, 0x0312, 0x0312, 1):
            if active and message.wParam in self.ids:
                result.append(self.ids[message.wParam])
        if not active:
            self.close()
        return result

    def close(self):
        for identifier in self.ids:
            self.user.UnregisterHotKey(None, identifier)
        self.ids.clear()
        self.attempted = False

    def game_foreground(self):
        window = self.user.GetForegroundWindow()
        if not window:
            return False
        pid = self.wt.DWORD()
        self.user.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if (window, pid.value) == self.foreground[:2]:
            return self.foreground[2]
        handle = self.kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return False
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = self.wt.DWORD(len(path))
            game = bool(self.kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length))
                        and Path(path.value).name.casefold() == 'deadlock.exe')
            self.foreground = (window, pid.value, game)
            return game
        finally:
            self.kernel.CloseHandle(handle)


@lru_cache(maxsize=32)
def font(size, ja=True, heading=False):
    game = os.environ.get('SPEC_HUD_GAME')
    if game:
        if ja:
            filename = 'tetsubingothic.otf' if heading else 'notosansjp-semibold.ttf'
        else:
            filename = 'valveoracle-semibold.ttf' if heading else 'valveoracle-medium.ttf'
        path = Path(game) / 'panorama' / 'fonts' / filename
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass
    return ImageFont.truetype(str(Path(__file__).with_name('fonts')/'NotoSansJP-Bold.ttf'), size)


def label(draw, xy, text, size=15, color='#ffefd7', anchor=None, *, ja=True, heading=False):
    face = font(size, ja, heading)
    draw.text((xy[0], xy[1]+1), text, font=face, fill='#000000', anchor=anchor)
    draw.text(xy, text, font=face, fill=color, anchor=anchor)


PANEL_HEADER_HEIGHT = 30


def panel_title(draw, x, y, text, ja, snapshot_clock=None):
    size = 15
    top, bottom = draw.textbbox((0, 0), text, font=font(size, ja))[1::2]
    title_y = y + (PANEL_HEADER_HEIGHT - top - bottom) // 2
    label(draw, (x+16, title_y), text, size, '#d6d3c9', ja=ja)
    if snapshot_clock is not None:
        clock = f'{snapshot_clock//60}:{snapshot_clock%60:02d}'
        stamp = f'{clock}時点' if ja else f'At {clock}'
        stamp_size = 12
        top, bottom = draw.textbbox((0, 0), stamp, font=font(stamp_size, ja))[1::2]
        stamp_y = y + (PANEL_HEADER_HEIGHT - top - bottom) // 2
        label(draw, (x+462, stamp_y), stamp, stamp_size, '#bdb8ab', 'ra', ja=ja)


def panel_background(draw, x, y):
    draw.rectangle((x, y, x+478, y+276), fill='#171915df', outline='#4b493f')
    draw.rectangle((x+1, y+1, x+477, y+PANEL_HEADER_HEIGHT-1), fill='#10130dee')
    draw.line((x+1, y+PANEL_HEADER_HEIGHT, x+477, y+PANEL_HEADER_HEIGHT), fill='#4b493f')


@lru_cache(maxsize=80)
def minimap_hero_icon(hero):
    path = Path(__file__).with_name('icons') / f'hero-mm-{int(hero)}.png'
    try:
        with Image.open(path) as source:
            face = ImageOps.contain(source.convert('RGBA'), (18, 18), Image.Resampling.LANCZOS)
    except OSError:
        return None
    mask = Image.new('L', (72, 72))
    ImageDraw.Draw(mask).ellipse((0, 0, 71, 71), fill=255)
    return face, mask.resize((18, 18), Image.Resampling.LANCZOS)


def team_title(draw, xy, team, title, size, ja, *, heading=False):
    if title:
        ja, heading = True, False
    else:
        title = team_name(team, ja)
    face = font(size, ja, heading)
    if draw.textlength(title, font=face) > 210:
        while title and draw.textlength(title + '…', font=face) > 210:
            title = title[:-1]
        title += '…'
    label(draw, xy, title, size, COLORS[team], ja=ja, heading=heading)


def damage_panel(image, x, y, rows, names, ja, titles, clock):
    draw = ImageDraw.Draw(image)
    panel_background(draw, x, y)
    panel_title(draw, x, y, '与ダメージ' if ja else 'Damage Dealt', ja, clock if rows else None)
    if not rows:
        label(draw,(x+16,y+70),'データ待ち' if ja else 'Waiting for data')
        return
    by_hero = {str(row[0]): row for row in rows}
    ordered = [(name, by_hero[hero]) for hero,name in names if hero in by_hero]
    maximum = max(1, max(row[2] for row in rows))
    for col,team in enumerate(COLORS):
        left = x+16+col*232
        color = COLORS[team]
        team_title(draw, (left, y+47), team, titles[col], 15, ja, heading=True)
        for index,(name,row) in enumerate(v for v in ordered if v[1][1] == team):
            top = y+73+index*31
            name = name or str(row[0])
            icon = minimap_hero_icon(row[0])
            if icon is not None:
                face, mask = icon
                badge = Image.new('RGBA', (18, 18), '#25251f')
                badge.alpha_composite(face, ((18-face.width)//2, (18-face.height)//2))
                image.paste(badge, (left, top), mask)
            amount = f'{row[2]:,}'
            name_width = min(121, 210 - 24 - 8 - font(15, ja).getlength(amount))
            while len(name)>1 and font(13, ja).getlength(name)>name_width:
                name=name[:-2]+'…'
            label(draw,(left+24,top),name,13,ja=ja)
            label(draw,(left+210,top+1),amount,15,anchor='ra',ja=ja)
            draw.rectangle((left,top+21,left+210,top+24),fill='#39372d')
            if row[2]:
                draw.rectangle((left,top+21,left+round(210*row[2]/maximum),top+24),fill=color)


def graph_panel(draw, x, y, history, clock, ja, titles):
    panel_background(draw, x, y)
    panel_title(draw, x, y, 'ソウル差' if ja else 'Soul Lead', ja, clock if history else None)
    left,right,middle,height=x+75,x+457,y+151,79
    team_title(draw, (left, y+47), 2, titles[0], 13, ja)
    team_title(draw, (left, y+226), 3, titles[1], 13, ja)
    draw.line((left,middle,right,middle),fill='#8b8473')
    label(draw,(left-8,middle),'0',12,'#d6d3c9','rm')
    end=max(1,clock)
    scale=max(1000,max((abs(d) for _,d in history),default=0))
    label(draw,(left-8,middle-height),f'+{scale/1000:.1f}k',11,'#d6d3c9','rm')
    label(draw,(left-8,middle+height),f'−{scale/1000:.1f}k',11,'#d6d3c9','rm')
    # Draw time ticks behind the lead curve so crossings stay readable.
    for second in range(300, clock+1, 300):
        tick = round(left+(right-left)*second/end)
        draw.line((tick, middle-4, tick, middle+4), fill='#c9c5b9')
        if second % (300*max(1, (clock+3599)//3600)) == 0 and right-tick >= 50:
            label(draw,(tick,y+246),f'{second//60}:00',10,'#c9c5b9','ma',ja=False)
    previous=None
    for second,lead in history:
        px=left+(right-left)*second/end
        py=middle-height*lead/scale
        if previous is not None and second==previous[0]+1:
            _,old,ox,oy=previous
            if old*lead<0:
                cross=ox+(px-ox)*abs(old)/(abs(old)+abs(lead))
                draw.line((ox,oy,cross,middle),fill=COLORS[2 if old>0 else 3],width=2)
                draw.line((cross,middle,px,py),fill=COLORS[2 if lead>0 else 3],width=2)
            else:
                draw.line((ox,oy,px,py),fill=COLORS[2 if old>0 or lead>=0 else 3],width=2)
        else:
            draw.ellipse((px-1,py-1,px+1,py+1),fill=COLORS[2 if lead>=0 else 3])
        previous=second,lead,px,py
    label(draw,(left,y+243),'0:00',12,'#c9c5b9')
    label(draw,(right,y+246),f'{clock//60}:{clock%60:02}',12,'#c9c5b9','ra',ja=False)
    if not history:
        label(draw,(left+10,y+85),'データ待ち' if ja else 'Waiting for data')
    elif history[-1][0] == clock:
        lead = history[-1][1]
        caption = (f'+{abs(lead):,}' if lead else ('同額' if ja else 'Tied'))
        label(draw,(right,y+53),caption,17,COLORS[2 if lead>0 else 3] if lead else '#ffefd7','ra',ja=ja)


@lru_cache(maxsize=6)
def panel_png(panel, rows, names, history, clock, ja, titles=('', '')):
    im = Image.new('RGBA', (480, 278) if panel else (1, 1))
    if panel == 'damage':
        damage_panel(im, 0, 0, rows, names, ja, titles, clock)
    elif panel == 'graph':
        graph_panel(ImageDraw.Draw(im), 0, 0, history, clock, ja, titles)
    output=io.BytesIO()
    im.save(output,format='PNG')
    return output.getvalue()

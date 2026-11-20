"""Render user-supplied team titles over the fixed spectator heading footprint."""
import base64
import binascii
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TITLES = {
    'ja': ('ヒドゥン・キング', 'アークマザー'),
    'en': ('The Hidden King', 'The Archmother'),
}
COLORS = ('#f6c769', '#b6caff')


def team_settings(home):
    try:
        with (home / 'team-headings.json').open('rb') as stream:
            raw = stream.read(256 * 1024 + 1)
        teams = json.loads(raw) if len(raw) <= 256 * 1024 else None
        if isinstance(teams, list) and len(teams) == 2 and all(isinstance(row, dict) for row in teams):
            return teams
    except (OSError, ValueError):
        pass
    return [{}, {}]


def clean_team_name(raw_name):
    return ''.join(c for c in raw_name[:64] if c.isprintable()).strip() if isinstance(raw_name, str) else ''


def team_setting(home, side):
    return team_settings(home)[side]


def series_png(home, assets):
    teams = team_settings(home)
    best_of = teams[0].get('BestOf')
    if type(best_of) is not int or best_of not in (3, 5):
        return b''
    slots = best_of // 2 + 1
    wins = [row.get('Wins', 0) for row in teams]
    if any(type(win) is not int or not 0 <= win <= slots for win in wins) or wins == [slots, slots]:
        return b''
    image = Image.new('RGBA', (672, 90))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(assets / 'fonts' / 'NotoSansJP-Bold.ttf'), 42)
    draw.text((336, 45), f'BO{best_of}', anchor='mm', font=font, fill='#f4f1e8')
    for side, direction in enumerate((-1, 1)):
        for index in range(slots):
            x = 336 + direction * (107 + index * 48)
            draw.ellipse((x-14, 31, x+14, 59), fill=COLORS[side] if index < wins[side] else None,
                         outline=COLORS[side], width=3)
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def custom_icon(encoded):
    if not isinstance(encoded, str) or not 0 < len(encoded) <= 88 * 1024:
        return None
    try:
        blob = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(blob), formats=['PNG']) as source:
            if source.size != (96, 96):
                return None
            icon = source.convert('RGBA')
            return icon if icon.getbbox() is not None else None
    except (binascii.Error, OSError, ValueError, Image.DecompressionBombError):
        return None


def team_bans_png(home, assets, side, language):
    ids = team_setting(home, side).get('Bans')
    if not isinstance(ids, list):
        return b''
    catalog = json.loads((Path(__file__).with_name('ban-heroes.json')).read_text(encoding='utf-8'))
    ids = list(dict.fromkeys(str(hero) for hero in ids[:6] if type(hero) is int and str(hero) in catalog))
    if not ids:
        return b''
    image = Image.new('RGBA', (600, 90))
    draw = ImageDraw.Draw(image)
    font_file = assets / 'fonts' / 'NotoSansJP-Bold.ttf'
    font = ImageFont.truetype(str(font_file), 36)
    width = 98 + 78 * len(ids)
    x = (image.width - width) // 2
    draw.text((x + 44, 45), 'BAN', anchor='mm', font=font, fill=COLORS[side])
    for index, hero in enumerate(ids):
        cx = x + 93 + 78 * index
        try:
            with Image.open(assets / 'icons' / f'hero-mm-{hero}.png') as source:
                face = source.convert('RGBA')
                face = face.resize((66, 66), Image.Resampling.LANCZOS)
                image.alpha_composite(face, (cx, (image.height-face.height)//2))
        except (OSError, ValueError):
            draw.text((cx+33, 45), catalog[hero][language][:2], anchor='mm',
                      font=ImageFont.truetype(str(font_file), 19), fill='#ffffff')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def team_header_png(home, assets, side, mode, language):
    row = team_setting(home, side)
    name = clean_team_name(row.get('Name')) if mode & 1 else ''
    icon = custom_icon(row.get('Icon')) if mode & 2 else None
    choice = row.get('Size')
    text_size, icon_size = ((16, 17), (19, 21), (22, 25))[choice if type(choice) is int and 0 <= choice <= 2 else 1]
    tone = COLORS[side]
    if mode & 1 and not name:
        name = TITLES[language][side]
    if mode & 2 and icon is None:
        try:
            with Image.open(assets / 'icons' / f'team{side+1}-header.png') as source:
                icon = Image.new('RGBA', source.size, tone)
                icon.putalpha(source.convert('RGBA').getchannel('A'))
        except (OSError, ValueError):
            return b''

    scale = 3
    image = Image.new('RGBA', (250 * scale, 30 * scale))
    ink = ImageDraw.Draw(image)
    width = 0
    if name:
        available = (232 - (icon_size + 6 if icon else 0)) * scale
        for size in range(text_size, 10, -1):
            font = ImageFont.truetype(str(assets / 'fonts' / 'NotoSansJP-Bold.ttf'), size * scale)
            if ink.textlength(name, font=font) <= available:
                break
        if ink.textlength(name, font=font) > available:
            while name and ink.textlength(name + '…', font=font) > available:
                name = name[:-1]
            name += '…'
        width = round(ink.textlength(name, font=font))
    icon_width = icon_size * scale if icon else 0
    gap = 6 * scale if icon and name else 0
    footprint = icon_width + gap + width
    x = (image.width - footprint) // 2
    if icon:
        icon.thumbnail((icon_width, icon_width), Image.Resampling.LANCZOS)
        image.alpha_composite(icon, (x + (icon_width - icon.width)//2, (image.height - icon.height)//2))
        x += icon_width + gap
    if name:
        ink.text((x, image.height//2), name, font=font, anchor='lm',
                 fill=tone, stroke_width=1, stroke_fill='#111618')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()

"""Draws the "System One AI Model" explainer GIF for LinkedIn (light, flat, pastel panels).

Every frame is drawn from a time value t, so the animation is deterministic.
Run: python make_gif.py            (writes out/decision-models-light.gif and out/poster-light.png)
     python make_gif.py --still 7  (writes out/still-7.0.png, to check one moment)
"""

from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
FONTS = ASSETS / "fonts"
OUT = HERE / "out"

W, H, S = 1200, 760, 2  # logical size, supersample factor
FRAME_MS = 70
T_END = 18.6
HOLD_MS = 2800

Color = tuple[int, int, int]

WHITE: Color = (255, 255, 255)
BG: Color = (245, 246, 243)  # warm paper
INK: Color = (17, 19, 24)
MUTED: Color = (98, 106, 104)
WIRE: Color = (168, 175, 170)
ROWLINE: Color = (224, 228, 223)
ROWFILL: Color = (247, 248, 246)
MINT: Color = (0, 255, 209)  # gauravlahoti.dev accent
TEAL: Color = (0, 140, 118)  # the same accent, darkened to read on light
TEAL_SOFT: Color = (214, 243, 235)
TEAL_EDGE: Color = (120, 208, 186)

# panel: (fill, border, label colour)
PANEL = (WHITE, (212, 217, 211), INK)

# the dark focal node
DARK: Color = (14, 17, 21)
DARK_ROW: Color = (29, 34, 40)
DARK_LINE: Color = (52, 60, 66)
DARK_ACTIVE: Color = (18, 52, 47)
DARK_MUTED: Color = (150, 160, 160)
DARK_TRACK: Color = (44, 50, 56)

# pills: (fill, outline, text)
PILL_Q = ((238, 240, 236), (200, 205, 198), (84, 92, 88))
PILL_A = (TEAL_SOFT, TEAL_EDGE, (0, 100, 84))
BAR: Color = TEAL
TRACK: Color = (222, 236, 231)
KW: Color = (190, 54, 108)
NUM: Color = (160, 92, 0)
FN: Color = (0, 120, 100)


def mix(a: Color, b: Color, k: float) -> Color:
    k = max(0.0, min(1.0, k))
    return (
        round(a[0] + (b[0] - a[0]) * k),
        round(a[1] + (b[1] - a[1]) * k),
        round(a[2] + (b[2] - a[2]) * k),
    )


def prog(t: float, start: float, dur: float) -> float:
    return max(0.0, min(1.0, (t - start) / dur))


def ease(p: float) -> float:
    return 1 - (1 - p) ** 3


def appear(t: float, start: float, dur: float = 0.5) -> float:
    """Quick pop-in: a long fade leaves washed-out ghosts on a light page, so keep it to ~2 frames."""
    return ease(prog(t, start, dur * 0.4))


def P(v: float) -> int:
    return round(v * S)


@lru_cache(maxsize=None)
def font(name: str, size: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), P(size))


def sans(size: float, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    return font(f"Inter-{weight}.ttf", size)


def mono(size: float) -> ImageFont.FreeTypeFont:
    return font("JetBrainsMono-Regular.ttf", size)


def tw(f: ImageFont.FreeTypeFont, s: str) -> float:
    return f.getlength(s) / S


def fit(s: str, max_w: float, size: float, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    while size > 11 and tw(sans(size, weight), s) > max_w:
        size -= 0.5
    return sans(size, weight)


class Canvas:
    def __init__(self) -> None:
        self.img = Image.new("RGB", (W * S, H * S), BG)
        self.d = ImageDraw.Draw(self.img)

    def rr(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        r: float,
        fill: Color | None,
        outline: Color | None = None,
        width: float = 1,
    ) -> None:
        self.d.rounded_rectangle(
            [P(x), P(y), P(x + w), P(y + h)],
            radius=P(r),
            fill=fill,
            outline=outline,
            width=max(1, P(width)),
        )

    def text(
        self, x: float, y: float, s: str, f: ImageFont.FreeTypeFont, fill: Color, anchor: str = "lm"
    ) -> None:
        self.d.text((P(x), P(y)), s, font=f, fill=fill, anchor=anchor)

    def dot(self, x: float, y: float, r: float, fill: Color) -> None:
        self.d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=fill)

    def line(self, pts: list[tuple[float, float]], color: Color, width: float = 2) -> None:
        if len(pts) < 2:
            return
        self.d.line([(P(x), P(y)) for x, y in pts], fill=color, width=P(width), joint="curve")
        for x, y in (pts[0], pts[-1]):
            self.dot(x, y, width / 2, color)

    def paste_rgba(self, im: Image.Image, x: float, y: float, alpha: float) -> None:
        if alpha <= 0:
            return
        if alpha < 1:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: round(v * alpha)))
        self.img.paste(im, (P(x), P(y)), im)


class Path2D:
    def __init__(self, pts: list[tuple[float, float]]) -> None:
        self.pts = pts
        self.segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        self.length = sum(self.segs)

    def upto(self, f: float) -> list[tuple[float, float]]:
        want = self.length * max(0.0, min(1.0, f))
        out = [self.pts[0]]
        for i, seg in enumerate(self.segs):
            a, b = self.pts[i], self.pts[i + 1]
            if want >= seg:
                out.append(b)
                want -= seg
            else:
                k = want / seg if seg else 0
                out.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
                break
        return out

    def at(self, f: float) -> tuple[float, float]:
        return self.upto(f)[-1]

    def arrow(self, c: Canvas, color: Color) -> None:
        (x0, y0), (x1, y1) = self.pts[-2], self.pts[-1]
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1
        dx, dy = dx / n, dy / n
        px, py = -dy, dx
        s = 8
        c.line(
            [
                (x1 - dx * s + px * s * 0.6, y1 - dy * s + py * s * 0.6),
                (x1, y1),
                (x1 - dx * s - px * s * 0.6, y1 - dy * s - py * s * 0.6),
            ],
            color,
            1.6,
        )


def pill(
    c: Canvas,
    x: float,
    y: float,
    label: str,
    colors: tuple[Color, Color, Color],
    base: Color,
    a: float = 1,
) -> float:
    f = mono(12.5)
    w = tw(f, label) + 20
    c.rr(x, y, w, 24, 12, mix(base, colors[0], a), mix(base, colors[1], a), 1)
    c.text(x + w / 2, y + 12.5, label, f, mix(base, colors[2], a), "mm")
    return w


def panel(
    c: Canvas,
    box: tuple[float, float, float, float],
    a: float,
    colors: tuple[Color, Color, Color],
    label: str,
    sub: str | None = None,
) -> None:
    if a < 0.03:
        return
    x, y, w, h = box
    dy = (1 - a) * 12
    c.rr(x, y + dy + 2, w, h, 18, mix(BG, (0, 0, 0), 0.05 * a))
    c.rr(x, y + dy, w, h, 18, mix(BG, colors[0], a), mix(BG, colors[1], a), 1.3)
    c.rr(x + 20, y + dy, 30, 4, 2, mix(colors[0], TEAL, a))
    c.text(x + 20, y + dy + 27, label, sans(14.5, "SemiBold"), mix(colors[0], colors[2], a))
    if sub:
        c.text(x + 20, y + dy + 46, sub, sans(12.5), mix(colors[0], MUTED, a))


def white_row(c: Canvas, x: float, y: float, w: float, h: float, base: Color, a: float) -> None:
    c.rr(x, y, w, h, 10, mix(base, ROWFILL, a), mix(base, ROWLINE, a), 1)


def icon_doc(c: Canvas, x: float, y: float, col: Color) -> None:
    c.rr(x, y, 13, 16, 2.5, None, col, 1.4)
    for i in range(3):
        c.line([(x + 3, y + 5 + i * 3.4), (x + 10, y + 5 + i * 3.4)], col, 1)


def icon_image(c: Canvas, x: float, y: float, col: Color) -> None:
    c.rr(x, y + 1, 16, 14, 2.5, None, col, 1.4)
    c.dot(x + 5, y + 6, 1.8, col)
    c.line([(x + 2.5, y + 13), (x + 7, y + 8.5), (x + 10, y + 11), (x + 12, y + 9), (x + 14, y + 12)], col, 1.2)


def icon_audio(c: Canvas, x: float, y: float, col: Color) -> None:
    for i, hgt in enumerate((5, 11, 15, 9, 5)):
        c.line([(x + 2 + i * 3.4, y + 8 - hgt / 2), (x + 2 + i * 3.4, y + 8 + hgt / 2)], col, 1.5)


def icon_video(c: Canvas, x: float, y: float, col: Color) -> None:
    c.rr(x, y + 1, 16, 14, 3, None, col, 1.4)
    c.d.polygon([(P(x + 6.5), P(y + 5)), (P(x + 6.5), P(y + 11)), (P(x + 11.5), P(y + 8))], fill=col)


PHOTO_BG: Color = (221, 226, 222)
PHOTO_FLOOR: Color = (204, 208, 201)
BOARD: Color = (203, 170, 125)
BOARD_EDGE: Color = (168, 136, 94)
BOARD_DENT: Color = (176, 144, 100)
TAPE: Color = (224, 198, 152)
CRACK: Color = (104, 76, 46)
DAMAGE = (0.50, 0.24, 0.80, 0.62)  # the Box answer: left, top, right, bottom as fractions of the photo


def photo(c: Canvas, x: float, y: float, w: float, h: float, box: tuple[float, float, float, float] | None = None) -> None:
    """A tiny photo of a damaged parcel, with an optional Box overlay (edges as fractions of the photo)."""
    c.rr(x, y, w, h, 6, PHOTO_BG, ROWLINE, 1)
    c.d.rectangle([P(x + 1.5), P(y + h * 0.74), P(x + w - 1.5), P(y + h - 3)], fill=PHOTO_FLOOR)
    px, py, pw, ph = x + w * 0.20, y + h * 0.30, w * 0.56, h * 0.55
    c.rr(px, py, pw, ph, 2, BOARD, BOARD_EDGE, 1)
    c.rr(px + pw * 0.45, py, pw * 0.10, ph, 0, TAPE)
    c.d.polygon([(P(px + pw), P(py)), (P(px + pw * 0.76), P(py)), (P(px + pw), P(py + ph * 0.30))], fill=BOARD_DENT)
    crack = [
        (px + pw * 0.80, py + ph * 0.04),
        (px + pw * 0.70, py + ph * 0.22),
        (px + pw * 0.82, py + ph * 0.34),
        (px + pw * 0.72, py + ph * 0.50),
    ]
    c.line(crack, CRACK, 1.2)
    if box:
        l, t, r, b = box
        c.d.rectangle([P(x + l * w), P(y + t * h), P(x + r * w), P(y + b * h)], outline=TEAL, width=P(1.7))
        for hx, hy in ((l, t), (r, t), (l, b), (r, b)):
            c.d.rectangle([P(x + hx * w - 2), P(y + hy * h - 2), P(x + hx * w + 2), P(y + hy * h + 2)], fill=TEAL)


# ---------------------------------------------------------------- layout
CTX = (40, 150, 350, 224)
QST = (40, 396, 350, 280)
MODEL = (500, 295, 200, 232)
ANS = (810, 150, 350, 358)
CODE = (810, 528, 350, 148)

IN1 = Path2D([(390, 262), (424, 262), (424, 386), (500, 386)])
IN2 = Path2D([(390, 536), (424, 536), (424, 436), (500, 436)])
ROWS_Y = [208, 282, 356, 430]
OUTS = [Path2D([(700, 411), (755, 411), (755, y + 33), (810, y + 33)]) for y in ROWS_Y]
TO_CODE = Path2D([(985, 508), (985, 528)])

BOTH = ("jev", "gem")
JEV_ONLY = ("jev",)

QUESTIONS = [
    ("noul", "Is this a refund request?", BOTH),
    ("choice", "Which team handles it?", BOTH),
    ("score", "How frustrated? (0 to 2)", BOTH),
    ("box", "Where is the damage?", JEV_ONLY),
]
ANSWERS = [
    ("noul", "refund_request: 0.97", "0.94"),
    ("choice", 'team: "returns"', "0.88"),
    ("score", "frustration: 1.4 / 2", "0.77"),
    ("box", "damage: box", "0.92"),
]

CAPTIONS = [
    (0.6, "Context and typed questions go in."),
    (2.6, "Jev reads text, JSON and images. Gemini Decision reads those plus PDF, audio and video."),
    (5.4, "Any mix of questions, one request. Each is scored in parallel, in isolation."),
    (8.9, "Typed answers return, each with a probability and a confidence score."),
    (12.4, "Your code branches, routes and sorts on them directly."),
    (15.4, "No text generated. Nothing to parse."),
    (18.0, "The takeaway: fast, low-cost judgment calls for Jev. Deep reasoning for your LLM."),
]
CAPTION_PT = 19  # one size for every caption; the longest one has to fit on a single line

# which model is "selected" while the capability beat plays (seconds)
JEV_PH = (2.7, 4.0)
GEM_PH = (3.85, 5.2)
ALL_PH = (2.7, 5.2)


def phase(t: float, span: tuple[float, float]) -> float:
    return min(prog(t, span[0], 0.15), 1 - prog(t, span[1] - 0.15, 0.15))


@lru_cache(maxsize=None)
def logo(name: str, size: int, on_light: bool = True) -> Image.Image:
    im = Image.open(ASSETS / name).convert("RGBA")
    if name == "jev-mark.png" and on_light:
        al = im.getchannel("A")
        dark = Image.new("RGB", im.size, INK)
        im = Image.merge("RGBA", (*dark.split(), al))
    return im.resize((P(size), P(size)), Image.LANCZOS)


def packet(c: Canvas, path: Path2D, p: float) -> None:
    if p <= 0 or p >= 1:
        return
    for i in range(6, 0, -1):
        q = max(0.0, p - i * 0.035)
        x, y = path.at(q)
        c.dot(x, y, 4.5 - i * 0.4, mix(BG, TEAL, 0.5 - i * 0.07))
    x, y = path.at(p)
    c.dot(x, y, 10, mix(BG, TEAL, 0.2))
    c.dot(x, y, 5, TEAL)


def draw_mark(c: Canvas, x: float, y: float, size: float, a: float = 1) -> None:
    """The gauravlahoti.dev node-link L (assets/img/logo.svg, 64 unit viewBox)."""
    k = size / 64
    ink = mix(BG, INK, a)

    def pt(px: float, py: float) -> tuple[float, float]:
        return (x + px * k, y + py * k)

    c.dot(*pt(18, 48), 12 * k, mix(BG, MINT, 0.22 * a))
    c.line([pt(18, 12), pt(18, 48), pt(48, 48)], ink, 4 * k)
    for cx, cy in ((18, 12), (48, 48)):
        c.dot(*pt(cx, cy), 7.5 * k, ink)
        c.dot(*pt(cx, cy), 3.5 * k, BG)
    c.dot(*pt(18, 48), 7 * k, mix(BG, MINT, a))


def render(t: float) -> Image.Image:
    c = Canvas()

    a = appear(t, 0.0, 0.6)
    label, lf, gap = "NEW MODEL CLASS", sans(12, "SemiBold"), 1.6
    lw = sum(tw(lf, ch) + gap for ch in label) - gap
    c.rr(600 - lw / 2 - 16, 24, lw + 32, 26, 13, mix(BG, DARK, a))
    lx = 600 - lw / 2
    for ch in label:
        c.text(lx, 37.5, ch, lf, mix(DARK, MINT, a))
        lx += tw(lf, ch) + gap
    c.text(600, 84, "System One AI Model", sans(40, "Bold"), mix(BG, INK, a), "mm")
    c.text(600, 120, "Fast, typed decisions your code can use directly.", sans(17), mix(BG, MUTED, a), "mm")
    draw_mark(c, 40, 30, 36, a)
    c.text(84, 49, "Gaurav Lahoti", mono(14.5), mix(BG, INK, a))

    # ---- context
    cf = PANEL[0]
    a = appear(t, 0.4, 0.6)
    panel(c, CTX, a, PANEL, "CONTEXT", "Logos show which model accepts each input")
    x, y, w, _ = CTX
    qa = appear(t, 0.9, 0.5)
    if qa >= 0.03:
        white_row(c, x + 16, y + 60, w - 32, 58, cf, qa)
        c.text(x + 32, y + 79, "Order arrived broken.", sans(17), mix(WHITE, INK, qa))
        c.text(x + 32, y + 101, "I want my money back.", sans(17), mix(WHITE, INK, qa))
        photo(c, x + w - 16 - 8 - 64, y + 68, 64, 42)

    jev_on = phase(t, JEV_PH)
    gem_on = phase(t, GEM_PH)
    all_on = phase(t, ALL_PH)

    def chips(row_y: float, items: list[tuple[str, object, tuple[str, ...]]], start: float) -> None:
        cx = x + 16
        f = sans(13.5, "Medium")
        for n, (label, icon, models) in enumerate(items):
            badge_w = len(models) * 14 + (len(models) - 1) * 4
            cw = 33 + tw(f, label) + 8 + badge_w + 8
            ka = appear(t, start + n * 0.15, 0.5)
            if ka >= 0.03:
                r = all_on if len(models) == 2 else gem_on
                fill = mix(mix(cf, ROWFILL, ka), TEAL_SOFT, r * 0.9)
                c.rr(cx, row_y, cw, 34, 10, fill, mix(mix(cf, ROWLINE, ka), TEAL, r), 1 + r * 1.2)
                if ka > 0.5:
                    icon(c, cx + 11, row_y + 9, mix(fill, MUTED, ka))
                c.text(cx + 33, row_y + 17.5, label, f, mix(fill, INK, ka))
                for j, m in enumerate(models):
                    mark = "jev-mark.png" if m == "jev" else "gemini-mark.png"
                    c.paste_rgba(logo(mark, 14), cx + cw - 8 - badge_w + j * 18, row_y + 10, ka)
            cx += cw + 8

    both = ("jev", "gem")
    chips(y + 132, [("Text & JSON", icon_doc, both), ("Image", icon_image, both)], 1.3)
    chips(y + 174, [("PDF", icon_doc, ("gem",)), ("Audio", icon_audio, ("gem",)), ("Video", icon_video, ("gem",))], 1.8)

    # ---- questions
    a = appear(t, 1.1, 0.6)
    panel(c, QST, a, PANEL, "TYPED QUESTIONS", "Logos show which model answers each type")
    x, y, w, _ = QST
    for i, (kind, text, models) in enumerate(QUESTIONS):
        ra = appear(t, 1.5 + i * 0.25, 0.5)
        if ra < 0.03:
            continue
        ry = y + 58 + i * 54 + (1 - ra) * 8
        r = all_on if len(models) == 2 else jev_on
        fill = mix(mix(PANEL[0], ROWFILL, ra), TEAL_SOFT, r * 0.9)
        c.rr(x + 16, ry, w - 32, 44, 10, fill, mix(mix(PANEL[0], ROWLINE, ra), TEAL, r), 1 + r * 1.2)
        pw = pill(c, x + 28, ry + 10, kind, PILL_Q, fill, ra)
        badge_w = len(models) * 14 + (len(models) - 1) * 4
        avail = w - 32 - 12 - pw - 22 - badge_w - 8
        c.text(x + 28 + pw + 10, ry + 22.5, text, fit(text, avail, 15.5), mix(fill, INK, ra))
        for j, m in enumerate(models):
            mark = "jev-mark.png" if m == "jev" else "gemini-mark.png"
            c.paste_rgba(logo(mark, 14), x + w - 16 - 10 - badge_w + j * 18, ry + 15, ra)

    # ---- input wires
    wf = prog(t, 5.6, 0.7)
    for path in (IN1, IN2):
        c.line(path.upto(ease(wf)), WIRE, 1.8)
        if wf >= 1:
            path.arrow(c, WIRE)
    la = appear(t, 5.8, 0.4)
    c.text(432, 372, "context", mono(12), mix(BG, MUTED, la), "lm")
    c.text(432, 452, "questions", mono(12), mix(BG, MUTED, la), "lm")

    # ---- model
    mx, my, mw, mh = MODEL
    ma = appear(t, 2.5, 0.7)
    pulse = 0.5 + 0.5 * math.sin((t - 6.9) * 5.5) if 6.9 <= t <= 8.9 else 0.0
    edge = mix((0, 120, 100), MINT, pulse if pulse else (0.35 if t > 8.9 else 0.0))
    my += (1 - ma) * 14  # slides up into place; fully opaque so it never passes through grey
    if ma >= 0.03:
        c.rr(mx, my + 3, mw, mh, 18, mix(BG, (0, 0, 0), 0.09 * 1.0))
        c.rr(mx, my, mw, mh, 18, mix(BG, DARK, 1.0), mix(BG, edge, 1.0), 2 if pulse else 1.6)
        c.text(mx + mw / 2, my + 28, "Decision Model", sans(19, "SemiBold"), mix(DARK, WHITE, 1.0), "mm")
        la = appear(t, 2.65, 0.6)
        for i, (mark, name) in enumerate((("jev-mark.png", "Jev"), ("gemini-mark.png", "Gemini Decision"))):
            if la < 0.03:
                continue
            by = my + 52 + i * 46
            act = jev_on if i == 0 else gem_on
            fill = mix(mix(DARK, DARK_ROW, la), DARK_ACTIVE, act)
            c.rr(mx + 14, by, mw - 28, 38, 10, fill, mix(mix(DARK, DARK_LINE, la), MINT, act), 1 + act * 1.2)
            c.paste_rgba(logo(mark, 22, False), mx + 26, by + 8, la)
            c.text(mx + 58, by + 19.5, name, sans(14.5, "SemiBold"), mix(fill, WHITE, la))
        c.text(mx + mw / 2, my + 160, "scores every question", sans(13), mix(DARK, DARK_MUTED, 1.0), "mm")
        c.text(mx + mw / 2, my + 177, "in parallel", sans(13), mix(DARK, DARK_MUTED, 1.0), "mm")
        for i, end in enumerate((8.1, 8.5, 8.9)):
            k = ease(prog(t, 7.0, end - 7.0))
            by = my + 193 + i * 8
            c.rr(mx + 34, by, mw - 68, 3.5, 1.75, mix(DARK, DARK_TRACK, 1.0))
            if k > 0:
                c.rr(mx + 34, by, max(3.5, (mw - 68) * k), 3.5, 1.75, MINT)

    packet(c, IN1, prog(t, 6.2, 0.7))
    packet(c, IN2, prog(t, 6.2, 0.7))

    # ---- output wires
    of = prog(t, 8.9, 0.5)
    for path in OUTS:
        c.line(path.upto(ease(of)), WIRE, 1.8)
        if of >= 1:
            path.arrow(c, WIRE)
    for i, path in enumerate(OUTS):
        packet(c, path, prog(t, 9.0 + i * 0.05, 0.6))

    # ---- answers
    a = appear(t, 9.2, 0.6)
    panel(c, ANS, a, PANEL, "TYPED ANSWERS", "Values, probabilities and confidence")
    if a >= 0.03:
        # latency chip: the stopwatch runs fast while the rest of the animation is slowed down to read
        # runs across the whole answer reveal: first row at 9.5 s, last row finished at 12.35 s
        k = prog(t, 9.5, 2.85)
        f = mono(12.5)
        label = "~100 ms" if k >= 1 else f"{round(100 * k)} ms"
        cw = 28 + tw(f, "~100 ms") + 12
        cx = ANS[0] + ANS[2] - 16 - cw
        cy = ANS[1] + 13 + (1 - a) * 12
        c.rr(cx, cy, cw, 26, 13, mix(WHITE, TEAL_SOFT, 1.0), mix(WHITE, TEAL_EDGE, 1.0), 1)
        ix, iy = cx + 15, cy + 14.5
        c.d.ellipse([P(ix - 5.5), P(iy - 5.5), P(ix + 5.5), P(iy + 5.5)], outline=TEAL, width=P(1.4))
        c.line([(ix, iy), (ix + 2.6, iy - 3)], TEAL, 1.2)
        c.rr(ix - 1.6, iy - 8.6, 3.2, 2.2, 0.8, TEAL)
        c.text(cx + 28, cy + 13.5, label, f, (0, 100, 84))
    for i, (kind, key, conf) in enumerate(ANSWERS):
        start = 9.5 + i * 0.55
        ra = appear(t, start, 0.5)
        if ra < 0.03:
            continue
        g = ease(prog(t, start + 0.3, 0.9))
        ry = ROWS_Y[i] + (1 - ra) * 8
        rx, rw = ANS[0] + 16, ANS[2] - 32
        white_row(c, rx, ry, rw, 66, PANEL[0], ra)
        pw = pill(c, rx + 14, ry + 10, kind, PILL_A, WHITE, ra)
        c.text(rx + 14 + pw + 10, ry + 22, key, sans(17, "Medium"), mix(WHITE, INK, ra))
        ly = ry + 50
        c.text(rx + 14, ly, "location" if kind == "box" else "probability", sans(12), mix(WHITE, MUTED, ra))
        bx = rx + 86
        bw = 96
        if kind == "noul":
            c.rr(bx, ly - 4, bw, 8, 4, mix(WHITE, TRACK, ra))
            if g > 0:
                c.rr(bx, ly - 4, max(8, bw * 0.97 * g), 8, 4, mix(WHITE, BAR, ra))
        elif kind == "choice":
            c.rr(bx, ly - 4, bw, 8, 4, mix(WHITE, TRACK, ra))
            limit, pos = bw * g, 0.0
            for share, col in ((0.91, BAR), (0.06, (150, 200, 160)), (0.03, (196, 222, 202))):
                seg = min(bw * share, max(0.0, limit - pos))
                if seg > 1:
                    c.rr(bx + pos, ly - 4, seg, 8, 3 if pos else 4, mix(WHITE, col, ra))
                pos += bw * share
        elif kind == "score":
            for j, p in enumerate((0.05, 0.50, 0.45)):
                hgt = max(3.0, 18 * (p / 0.5) * g)
                c.rr(bx + j * 32, ly + 6 - hgt, 26, hgt, 3, mix(WHITE, BAR, ra * (1.0 if j == 1 else 0.5)))
        else:
            # the box narrows from the whole photo onto the damage
            edges = tuple(o + (d - o) * g for o, d in zip((0, 0, 1, 1), DAMAGE))
            photo(c, rx + rw - 14 - 80, ry + 9, 80, 48, edges)
        if kind == "box":
            c.text(bx, ly, "confidence: " + conf, sans(12), mix(WHITE, MUTED, ra), "lm")
        else:
            c.text(rx + rw - 14, ly, "confidence: " + conf, sans(12), mix(WHITE, MUTED, ra), "rm")

    # ---- code
    ta = prog(t, 12.2, 0.3)
    c.line(TO_CODE.upto(ease(ta)), WIRE, 1.8)
    if ta >= 1:
        TO_CODE.arrow(c, WIRE)
    a = appear(t, 12.4, 0.6)
    panel(c, CODE, a, PANEL, "YOUR CODE")
    cx0 = CODE[0] + 16
    lines = [
        ("branch", [("if", KW), (" refund_request ", INK), (">", MUTED), (" ", INK), ("0.7", NUM), (":", MUTED)]),
        ("route", [("    ", INK), ("route", FN), ("(team)", INK)]),
        ("sort", [("queue", INK), (".sort", FN), ("(by=frustration)", INK)]),
        ("evidence", [("attach", FN), ("(photo, damage)", INK)]),
    ]
    sizes = [sum(len(x) for x, _ in toks) for _, toks in lines]
    total = sum(sizes)
    typed = int(max(0.0, t - 12.8) / 2.2 * total)
    f = mono(14)
    done_at = 12.8
    left = typed
    for li, (tag, toks) in enumerate(lines if a > 0.05 else []):
        ry = CODE[1] + 36 + li * 27
        done_at += 2.2 * sizes[li] / total
        hl = appear(t, done_at, 0.4)
        white_row(c, CODE[0] + 12, ry, CODE[2] - 24, 23, PANEL[0], a)
        if hl > 0:
            c.rr(CODE[0] + 12, ry, CODE[2] - 24, 23, 9, mix(WHITE, PILL_A[0], hl), mix(WHITE, PILL_A[1], hl), 1)
            c.text(CODE[0] + CODE[2] - 24, ry + 12, tag, mono(12), mix(WHITE, PILL_A[2], hl), "rm")
        px = cx0 + 4
        for text, col in toks:
            if left <= 0:
                break
            piece = text[:left]
            left -= len(piece)
            c.text(px, ry + 12, piece, f, mix(WHITE, col, a))
            px += tw(f, piece)

    # ---- caption
    for i, (s, text) in enumerate(CAPTIONS):
        end = CAPTIONS[i + 1][0] if i + 1 < len(CAPTIONS) else 1e9
        al = min(appear(t, s, 0.4), 1 - prog(t, end - 0.3, 0.3))
        if al > 0:
            c.text(600, 711, text, font("Roboto-Regular.ttf", CAPTION_PT), mix(BG, INK, al), "mm")

    # ---- footer
    fa = appear(t, 0.6, 0.6)
    c.text(40, 742, "Illustrative values", sans(12), mix(BG, MUTED, fa))
    c.text(1160, 742, "gauravlahoti.dev", mono(12.5), mix(BG, INK, fa * 0.75), "rm")

    return c.img.resize((W, H), Image.LANCZOS)


def build_palette(frames: list[Image.Image]) -> Image.Image:
    """Ramps for every flat colour over each background, then median cut for the rest."""
    light = [TEAL, INK, MUTED, WIRE, PILL_Q[2], PILL_A[2], KW, NUM, FN, MINT, (57, 123, 247), (156, 111, 228)]
    dark = [MINT, WHITE, DARK_MUTED, TEAL, (57, 123, 247), (156, 111, 228)]
    colours: list[Color] = [BG, WHITE, INK, PHOTO_BG, PHOTO_FLOOR, BOARD, BOARD_EDGE, BOARD_DENT, TAPE, CRACK]
    for base in (BG, WHITE, TEAL_SOFT):
        for acc in light:
            for k in (0.2, 0.45, 0.7, 1.0):
                colours.append(mix(base, acc, k))
    for base in (DARK, DARK_ROW, DARK_ACTIVE):
        for acc in dark:
            for k in (0.25, 0.5, 0.75, 1.0):
                colours.append(mix(base, acc, k))
    colours = list(dict.fromkeys(colours))[:216]
    sample = frames[:: max(1, len(frames) // 12)] + [frames[-1]]
    sheet = Image.new("RGB", (W, H * len(sample)))
    for i, fr in enumerate(sample):
        sheet.paste(fr, (0, H * i))
    rest = sheet.quantize(256 - len(colours), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    raw = rest.getpalette() or []
    merged: list[int] = []
    for col in colours:
        merged.extend(col)
    merged.extend(raw[: (256 - len(colours)) * 3])
    merged.extend([0] * (768 - len(merged)))
    pal = Image.new("P", (1, 1))
    pal.putpalette(merged)
    return pal


def snap(src: Image.Image, quant: Image.Image) -> Image.Image:
    """Palette lookup is approximate, so pin exact page-background and white pixels to their palette slots."""
    for slot, col in ((0, BG), (1, WHITE)):
        r, g, b = (ch.point(lambda v, tgt=tgt: 255 if v == tgt else 0) for ch, tgt in zip(src.split(), col))
        quant.paste(slot, mask=ImageChops.multiply(ImageChops.multiply(r, g), b))
    return quant


def build_gif() -> None:
    OUT.mkdir(exist_ok=True)
    step = FRAME_MS / 1000
    times = [i * step for i in range(int(T_END / step) + 1)]
    frames = [render(t) for t in times]
    frames[-1].save(OUT / "poster-light.png")
    pal = build_palette(frames)
    q = [snap(fr, fr.quantize(palette=pal, dither=Image.Dither.NONE)) for fr in frames]
    durations = [FRAME_MS] * (len(q) - 1) + [HOLD_MS]
    target = OUT / "decision-models-light.gif"
    q[0].save(target, save_all=True, append_images=q[1:], duration=durations, loop=0, optimize=False, disposal=1)
    print(f"{len(q)} frames, {target.stat().st_size / 1_000_000:.2f} MB -> {target}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--still":
        OUT.mkdir(exist_ok=True)
        tt = float(sys.argv[2])
        render(tt).save(OUT / f"still-{tt}.png")
        print(OUT / f"still-{tt}.png")
    else:
        build_gif()

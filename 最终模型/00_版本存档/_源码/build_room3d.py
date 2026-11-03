# -*- coding: utf-8 -*-
"""
build_room3d.py —— 按现场照片重建的「上床下桌」结构模型  v2
================================================================
只保留家具与建筑结构，去掉所有物品。

本版改动：
    · 右侧书架落在书桌右端，与桌下柜是同一个柜体（上下贯通）
    · 右侧书架：三个等分开放格，最下一层与桌面齐平
    · 右侧柜体与衣柜等高（FURN_H）
    · 门可以打开：衣柜双开门、桌下柜门；抽屉可抽出

尺寸：书桌 90 × 56 实测，其余按照片估算，都在 DIMS 里标了。
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_desk3d as bd
from build_desk3d import _font, decollide

ROOT = os.path.dirname(os.path.abspath(__file__))

# ================================================================
DIMS = {
    "DESK_W": 135.0,     # 实测：桌面长
    "DESK_D": 56.0,      # 实测
    "DESK_H": 75.0,      # 实测
    "TOP_T": 2.5,        # 实测：桌板厚
    "DRAWER_W": 32.0,    # 实测：桌下小抽屉宽

    "WARD_W": 80.0,      # 实测：衣柜宽
    "WARD_D": 58.5,      # 实测：衣柜深
    "WARD_DOOR_W": 40.0, # 实测：衣柜门宽（衣柜右侧）
    "FURN_H": 168.0,     # 估算：衣柜与右侧柜体等高，顶到床沿挡板下方

    "COL_W": 47.0,       # 估算：右侧贯通柜宽度
    "COL_D": 24.5,       # 估算：书架进深

        "BED_W": 210.0,     # 实测：床长
    "BED_D": 92.0,      # 实测：床宽
    "BED_Y": 186.0,
    "BED_T": 5.0,
        "RAIL_GAP": 45.0,
    "LADDER_Z0": 66.0,   # 估算：梯子前沿，左侧护栏到这里为止   # 估算：护栏上人开口宽度
    "BED_RAIL": 26.0,

    "HUTCH_W": 88.0,     # 估算：桌上书架宽度（桌面长 − 右侧柜宽）
    "HUTCH_D": 24.5,
    "HUTCH_P": 2.0,      # 实测：中间层板厚
    "HUTCH_LIP": 5.0,    # 实测：中层板前沿那道挡板高
    "HUTCH_TIER": 53.0,   # 实测：下层净高（桌面 → 中层板底）
    "HUTCH_H": 80.0,

    "PANEL": 1.8,
    "STEEL": 4.0,
}

P = DIMS["PANEL"]
ST = DIMS["STEEL"]

C_WOOD    = (208, 170, 120)
C_WOOD_D  = (178, 140, 94)
C_WOOD_L  = (224, 192, 148)
C_STEEL   = (150, 154, 160)
C_WHITE = (236, 236, 231)
C_BLACK = (46, 47, 52)
C_BLACK_L = (32, 33, 38)
C_STEEL_L = (174, 178, 184)
C_WALL    = (243, 241, 235)
C_FLOOR   = (172, 112, 96)

C_SCREEN  = (54, 60, 70)
C_BEZEL   = (28, 30, 34)
C_KEY     = (56, 58, 64)
C_MAT     = (42, 44, 50)
C_SPK     = (52, 54, 60)
C_LEAF    = (88, 122, 78)
C_POT     = (124, 92, 68)
C_ORG     = (204, 196, 184)
C_CERAMIC = (226, 222, 212)

G_BED = "床架"
G_STAIR = "床梯"
G_WARD = "衣柜"
G_DESK = "书桌"
G_COL = "右侧贯通柜"
G_HUTCH = "桌上书架"
G_LIMB = "可选配件"
G_ENV = "环境"

FACES = []
FACE_DOOR = []
ANNOTS = []

DOORS_BASE = [
    {"id": "ward_top", "label": "衣柜顶柜门", "kind": "swing",
     "hx": -DIMS["WARD_DOOR_W"], "hz": DIMS["WARD_D"], "sign": 1, "max": 100},
    {"id": "ward_main", "label": "衣柜主柜门", "kind": "swing",
     "hx": -DIMS["WARD_DOOR_W"], "hz": DIMS["WARD_D"], "sign": 1, "max": 95},
    {"id": "cab", "label": "侧柜门", "kind": "swing",
     "hx": DIMS["DESK_W"] - 2.0, "hz": DIMS["DESK_D"] - 2.0,
     "sign": -1, "max": 95},
    {"id": "drawer", "label": "抽屉", "kind": "slide", "max": 28.0},
]

X_WARD0, X_WARD1 = -DIMS["WARD_W"], 0.0
X_D0, X_D1 = 0.0, DIMS["DESK_W"]
X_C0 = X_D1 - DIMS["COL_W"]
X_C1 = X_D1

CUR_DOOR = None
DOOR_TAG = True
FACE_META = []
ALL_DOORS = []
BOXES = []
UNIT_XFORMS = []
CUR_UNIT = 0
CUR_SLOT = None
XFORM = {"sx": 1, "sz": 1, "ox": 0.0, "oz": 0.0}


def _tf(p):
    return (XFORM["sx"] * p[0] + XFORM["ox"], p[1], XFORM["sz"] * p[2] + XFORM["oz"])


def quad(p0, p1, p2, p3, color, group):
    p0, p1, p2, p3 = _tf(p0), _tf(p1), _tf(p2), _tf(p3)
    if XFORM["sx"] * XFORM["sz"] < 0:          # 镜像时反转绕序，法线才不会反向
        p1, p3 = p3, p1
    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    vx, vy, vz = p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    FACES.append(((p0, p1, p2, p3), (nx / L, ny / L, nz / L), color, group))
    FACE_DOOR.append((str(CUR_UNIT) + "|" + CUR_DOOR) if CUR_DOOR else None)
    FACE_META.append((CUR_UNIT, CUR_SLOT[0] if CUR_SLOT else None,
                       CUR_SLOT[1] if CUR_SLOT else None))


def box(x0, x1, y0, y1, z0, z1, color, group, skip=()):
    if x1 <= x0 or y1 <= y0 or z1 <= z0:
        return
    _xs = sorted((XFORM["sx"] * x0 + XFORM["ox"], XFORM["sx"] * x1 + XFORM["ox"]))
    _zs = sorted((XFORM["sz"] * z0 + XFORM["oz"], XFORM["sz"] * z1 + XFORM["oz"]))
    BOXES.append((_xs[0], _xs[1], y0, y1, _zs[0], _zs[1], group, CUR_DOOR, CUR_UNIT,
                  (CUR_SLOT[0] + ":" + CUR_SLOT[1]) if CUR_SLOT else None))
    if "right" not in skip:
        quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), color, group)
    if "left" not in skip:
        quad((x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0), color, group)
    if "top" not in skip:
        quad((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), color, group)
    if "bottom" not in skip:
        quad((x0, y0, z1), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), color, group)
    if "front" not in skip:
        quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), color, group)
    if "back" not in skip:
        quad((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), color, group)


def build_env():
    box(-340, 180, -2, 0, -20, 340, C_FLOOR, G_ENV, skip=("bottom",))
    box(-340, 180, 0, 240, -4, 0, C_WALL, G_ENV, skip=("bottom", "top", "front"))
    box(-340, 180, 0, 240, 320, 324, C_WALL, G_ENV, skip=("bottom", "top", "back"))

def build_bed():
    """金属床架：床 200 × 92，架在家具上方，前沿超出桌沿"""
    y = DIMS["BED_Y"]
    x0, x1 = X_C1 - DIMS["BED_W"], X_C1        # 右沿对齐书桌右沿
    z0, z1 = 0.0, DIMS["BED_D"]

    for lx in (x0, x1 - ST):
        for lz in (z0, z1 - ST):
            box(lx, lx + ST, 0, y + DIMS["BED_T"], lz, lz + ST, C_STEEL, G_BED,
                skip=("top", "bottom"))
    box(x0, x1, y - ST, y, z0, z0 + ST, C_STEEL, G_BED, skip=("top", "bottom"))
    box(x0, x1, y - ST, y, z1 - ST, z1, C_STEEL, G_BED, skip=("top", "bottom"))
    box(x0, x0 + ST, y - ST, y, z0, z1, C_STEEL, G_BED, skip=("top", "bottom"))
    box(x1 - ST, x1, y - ST, y, z0, z1, C_STEEL, G_BED, skip=("top", "bottom"))
    box(x0, x1, y - 3, y - 1, (z0 + z1) / 2 - 1.5, (z0 + z1) / 2 + 1.5,
        C_STEEL_L, G_BED, skip=("top", "bottom"))
    box(x0 + ST, x1 - ST, y, y + DIMS["BED_T"], z0 + ST, z1 - ST, C_WOOD_L, G_BED)

    # 床沿木挡板（只覆盖家具这一段，正面那道橙木板）
    box(X_D0, X_C1, y - 18.0, y, z1 - 3.2, z1 - 1.2, C_WOOD, G_BED,
        skip=("bottom",))
    # 床下纵向横梁
    for k in (0.32, 0.68):
        zz = z0 + (z1 - z0) * k
        box(x0 + ST, x1 - ST, y - 5.0, y - 3.0, zz - 1.2, zz + 1.2,
            C_STEEL_L, G_BED, skip=("top", "bottom"))

    # 四边护栏：前、后、左、右；前面左端和左面靠梯子那段留上人开口
    fy0 = y + DIMS["BED_T"]
    fy1 = fy0 + DIMS["BED_RAIL"]
    rx0 = x0 + DIMS["RAIL_GAP"]          # 前护栏开口右沿
    rw = 2.4                             # 栏杆截面

    def rail_x(xa, xb, zc):
        """沿 x 方向的护栏，栏杆占 zc-rw .. zc"""
        if xb - xa < 10.0:
            return
        box(xa, xb, fy1 - 3.0, fy1, zc - rw, zc, C_STEEL, G_BED,
            skip=("bottom",))
        n = max(2, int(round((xb - xa) / 32.0)))
        for i in range(n + 1):
            px = xa + (xb - xa - 2.0) * i / n
            box(px, px + 2.0, fy0, fy1, zc - rw, zc, C_STEEL, G_BED,
                skip=("top", "bottom"))

    def rail_z(za, zb, xc):
        """沿 z 方向的护栏，栏杆占 xc-rw .. xc"""
        if zb - za < 10.0:
            return
        box(xc - rw, xc, fy1 - 3.0, fy1, za, zb, C_STEEL, G_BED,
            skip=("bottom",))
        n = max(2, int(round((zb - za) / 32.0)))
        for i in range(n + 1):
            pz = za + (zb - za - 2.0) * i / n
            box(xc - rw, xc, fy0, fy1, pz, pz + 2.0, C_STEEL, G_BED,
                skip=("top", "bottom"))

    rail_x(rx0, x1, z1)                  # 前面（右段，左端是上人口）
    rail_x(x0 + rw, x1 - rw, z0 + rw)    # 后面（贴墙那侧）
    rail_z(z0 + rw, z1 - rw, x1)         # 右面
    rail_z(z0 + rw, DIMS["LADDER_Z0"], x0 + rw)   # 左面：到梯子处为止

    # 开口处那根立柱，稍高一点，当作扶手端头
    for ex in (rx0 - rw, rx0 + 0.6):
        box(ex, ex + 1.8, fy0, fy1 + 6.0, z1 - rw, z1, C_STEEL, G_BED,
            skip=("top", "bottom"))
    box(x0, x0 + rw, fy0, fy1 + 6.0, DIMS["LADDER_Z0"] - 1.8,
        DIMS["LADDER_Z0"], C_STEEL, G_BED, skip=("top", "bottom"))



def build_shared_ladder(cx, z0, z1, ytop, tag=True):
    """两个床位共用的梯子，居中在 cx"""
    global CUR_DOOR
    xa, xb = cx - 20.0, cx + 20.0
    for lx in (xa, xb - 3.0):
        box(lx, lx + 3.0, 0, ytop, z0, z1, C_STEEL, G_STAIR,
            skip=("top", "bottom"))
    for i in range(5):
        yy = 16.0 + i * 33.0
        if yy + 3.0 > ytop - 12.0:
            break
        box(xa + 1.0, xb - 1.0, yy, yy + 3.0, z0 + 1.0, z1 - 1.0,
            C_STEEL_L, G_STAIR, skip=("bottom",))
    # 顶部连接杆
    box(xa - 6.0, xb + 6.0, ytop - 9.0, ytop - 5.0, z0 + 6.0, z0 + 10.0,
        C_STEEL, G_STAIR, skip=("top", "bottom"))
    # 侧向支撑杆
    box(xb, xb + 14.0, 46.0, 49.0, z0 + 7.0, z0 + 10.0, C_STEEL, G_STAIR,
        skip=("top", "bottom"))
    box(xb + 11.0, xb + 14.0, 0, 49.0, z0 + 7.0, z0 + 10.0, C_STEEL, G_STAIR,
        skip=("top", "bottom"))

def build_ward():
    """衣柜：门只占右侧 40cm，上下两扇；左侧是固定面板"""
    global CUR_DOOR
    x0, x1 = X_WARD0, X_WARD1
    z0, z1 = 0.0, DIMS["WARD_D"]
    y1 = DIMS["FURN_H"]
    seam = y1 - 45.0
    dw = DIMS["WARD_DOOR_W"]
    dx0 = x1 - dw                      # 门的左沿

    # 箱体：左/右/背/底/顶 五面壳，正面留空给门
    box(x0, x0 + P, 0, y1, z0, z1 - 1.2, C_WOOD, G_WARD,
        skip=("top", "bottom"))                                    # 左侧板
    box(x1 - P, x1, 0, y1, z0, z1 - 1.2, C_WOOD, G_WARD,
        skip=("top", "bottom"))                                    # 右侧板
    box(x0, x1, 0, y1, z0, z0 + 1.0, C_WOOD_L, G_WARD,
        skip=("bottom", "top", "left", "right"))                   # 背板
    box(x0, x1, 0, P, z0, z1 - 1.2, C_WOOD, G_WARD, skip=("bottom",))       # 底板
    box(x0, x1, y1 - P, y1, z0, z1 - 1.2, C_WOOD, G_WARD, skip=("top",))    # 顶板
    # 底部深色踢脚
    box(x0 + 1, x1 - 1, 0, 8, z1 - 1.4, z1, C_WOOD_D, G_WARD,
        skip=("top", "bottom", "back"))
    # 内部：中隔板 + 挂衣杆
    box(x0 + 1, x1 - 1, seam - P, seam, z0 + 1, z1 - 1.4, C_WOOD_D, G_WARD,
        skip=("bottom",))
    box(x0 + 4, x1 - 4, seam - 15, seam - 13, (z0 + z1) / 2 - 1.2,
        (z0 + z1) / 2 + 1.2, C_STEEL_L, G_WARD, skip=("top", "bottom"))
    # 顶封边
    box(x0 + 1, x1 - 1, y1 - 3, y1, z1 - 1.2, z1 + 0.2, C_WOOD_D, G_WARD,
        skip=("bottom",))

    # 左侧固定面板（不是门）
    box(x0 + 1.5, dx0 - 1.0, 9, y1 - 4, z1 - 1.2, z1 + 0.1, C_WOOD_L, G_WARD)
    # 固定面板中间一道竖缝，做成一整块的观感
    box(dx0 - 1.0, dx0 - 0.4, 9, y1 - 4, z1 - 0.2, z1 + 0.15, C_WOOD_D, G_WARD,
        skip=("top", "bottom", "left", "right", "back"))

    # 顶柜门（单开，铰链在门的左沿）
    CUR_DOOR = ("ward_top" if DOOR_TAG else None)
    box(dx0, x1 - 0.6, seam + 1.5, y1 - 4, z1 - 1.2, z1 + 0.2, C_WOOD_L, G_WARD)
    box(x1 - 9.5, x1 - 7.8, seam + 9, seam + 21, z1 + 0.2, z1 + 1.6,
        C_STEEL_L, G_WARD, skip=("top", "bottom", "left", "right", "back"))
    CUR_DOOR = None

    # 主柜门（单开，铰链在门的左沿）
    CUR_DOOR = ("ward_main" if DOOR_TAG else None)
    box(dx0, x1 - 0.6, 9, seam - 1.5, z1 - 1.2, z1 + 0.2, C_WOOD_L, G_WARD)
    box(x1 - 9.5, x1 - 7.8, seam * 0.55 - 7, seam * 0.55 + 7, z1 + 0.2, z1 + 1.6,
        C_STEEL_L, G_WARD, skip=("top", "bottom", "left", "right", "back"))
    CUR_DOOR = None

def build_desk():
    x0, x1 = X_D0, X_D1
    z0, z1 = 0.0, DIMS["DESK_D"]
    h, t = DIMS["DESK_H"], DIMS["TOP_T"]
    box(x0, x1, h - t, h, z0, z1, C_WOOD, G_DESK)
    box(x0, x1, h - t - 0.6, h - t, z1 - 1.2, z1, C_WOOD_D, G_DESK,
        skip=("top", "bottom"))


def build_column():
    """右侧贯通柜体：地面 → 顶，一整件
    下部是封闭柜（带门），桌面高度处一块层板，上部三个等分开放格。
    顶面与衣柜等高。"""
    global CUR_DOOR
    x0, x1 = X_C0, X_C1
    h = DIMS["DESK_H"]
    t = DIMS["TOP_T"]
    top = DIMS["FURN_H"]
    zd = DIMS["COL_D"]                 # 上部格架进深
    zf = DIMS["DESK_D"] - 2.0          # 下部柜体进深（齐着桌沿）

    # 左右侧板：下段深、上段浅，一体
    for px in (x0, x1 - P):
        box(px, px + P, 0, h, 0, zf, C_WOOD_D, G_COL, skip=("top", "bottom"))
        box(px, px + P, h, top, 0, zd, C_WOOD_D, G_COL, skip=("top", "bottom"))
    # 背板
    box(x0, x1, 0, top, 0, 1.0, C_WOOD_L, G_COL,
        skip=("bottom", "top", "left", "right"))
    # 底板 / 顶板
    box(x0, x1, 0, P, 2.0, zf, C_WOOD, G_COL)
    box(x0, x1, top - P, top, 0, zd, C_WOOD, G_COL, skip=("bottom",))

    # 柜门（下部，铰链在左沿）
    CUR_DOOR = ("cab" if DOOR_TAG else None)
    box(x0 + 2.0, x1 - 2.0, P + 2, h - t - 4, zf - 0.4, zf + 0.8, C_WOOD_L, G_COL)
    box(x0 + 5.5, x0 + 7.3, h * 0.55 - 8, h * 0.55 + 8, zf + 0.8, zf + 2.4,
        C_STEEL_L, G_COL, skip=("top", "bottom", "left", "right", "back"))
    CUR_DOOR = None

    # 桌面高度那块层板：与桌面齐平
    box(x0, x1, h, h + P, 0, zd, C_WOOD, G_COL, skip=("bottom", "top"))
    # 上部三个等分
    step = (top - (h + P)) / 3.0
    for i in (1, 2):
        yy = h + P + i * step
        box(x0, x1, yy, yy + P, 0, zd, C_WOOD, G_COL, skip=("bottom",))

def build_drawer():
    """桌下小抽屉：五块板拼的上口敞开盒，拉出来能看见里面"""
    global CUR_DOOR
    h, t = DIMS["DESK_H"], DIMS["TOP_T"]
    yd = h - t
    dx0 = X_D0 + 2.0
    dx1 = dx0 + DIMS["DRAWER_W"]
    y0, y1 = yd - 16.3, yd - 1.3          # 顶面留 0.7 净空，避开桌面下沿收边
    z0, z1 = 3.0, 51.0
    T = 1.2

    CUR_DOOR = ("drawer" if DOOR_TAG else None)
    box(dx0, dx1, y0, y0 + T, z0, z1, C_WOOD_D, G_DESK)                 # 底板
    box(dx0, dx1, y0, y1, z0, z0 + T, C_WOOD, G_DESK)                   # 后板
    box(dx0, dx0 + T, y0, y1, z0, z1, C_WOOD, G_DESK,
        skip=("top", "bottom"))                                          # 左板
    box(dx1 - T, dx1, y0, y1, z0, z1, C_WOOD, G_DESK,
        skip=("top", "bottom"))                                          # 右板
    box(dx0, dx1, y0, y1, z1, z1 + 1.4, C_WOOD_L, G_DESK)               # 前面板
    cx = (dx0 + dx1) / 2.0
    box(cx - 5.0, cx + 5.0, y0 + 4.0, y0 + 6.0, z1 + 1.4, z1 + 2.4,
        C_STEEL_L, G_DESK, skip=("top", "bottom", "left", "right", "back"))
    CUR_DOOR = None

def build_hutch():
    """左侧桌上书架：上下两个大区，没有底板——下层直接通到桌面
    顶面与右侧贯通柜、衣柜三者在同一高度"""
    x0, x1 = X_D0, X_D0 + DIMS["HUTCH_W"]
    zd = DIMS["HUTCH_D"]
    h = DIMS["DESK_H"]
    top = DIMS["FURN_H"]

    # 中间层板（实测厚 2）：下层净高 53，上层净高 36
    hp = DIMS["HUTCH_P"]
    ymid = h + DIMS["HUTCH_TIER"]
    box(x0, x1, ymid, ymid + hp, 0, zd, C_WOOD, G_HUTCH)
    # 前沿挡板：高 5，贴在中层板前面
    box(x0, x1, ymid + hp - DIMS["HUTCH_LIP"], ymid + hp,
        zd - 2.2, zd, C_WOOD_D, G_HUTCH)
    # 顶板
    box(x0, x1, top - P, top, 0, zd, C_WOOD, G_HUTCH)
    # 两侧板：从桌面直上到顶，不设底板
    box(x0, x0 + P, h, top - P, 0, zd, C_WOOD_D, G_HUTCH, skip=("top", "bottom"))
    box(x1 - P, x1, h, top - P, 0, zd, C_WOOD_D, G_HUTCH, skip=("top", "bottom"))
    # 背板
    box(x0, x1, h, top - P, 0, 1.0, C_WOOD_L, G_HUTCH,
        skip=("bottom", "top", "left", "right"))

BOARD_W = 30.0                      # 宽（进深方向）固定 30
BOARD_H = {"60": 60.0, "80": 80.0}   # 长（竖直方向）可选


def _build_board(kind, size):
    """一块挂在衣柜侧面的板：kind=peg/felt，size=s/m/l"""
    global CUR_SLOT
    CUR_SLOT = ("board", kind + "_" + size)
    h, d = BOARD_H[size], BOARD_W
    cyc, czc = 118.0, 40.0
    y0, y1 = cyc - h / 2.0, cyc + h / 2.0
    z0, z1 = czc - d / 2.0, czc + d / 2.0
    bx0, bx1 = 0.2, 1.4
    fw = 1.6
    if kind == "peg":
        body, edge, hole = (200, 174, 140), (150, 126, 96), (106, 90, 70)
    else:
        body, edge, hole = (146, 154, 158), (94, 102, 106), None

    box(bx0, bx1, y0, y1, z0, z1, body, G_LIMB)
    box(bx0 - 0.12, bx1 + 0.16, y0, y0 + fw, z0 - 0.12, z1 + 0.12, edge, G_LIMB,
        skip=("top", "bottom"))
    box(bx0 - 0.12, bx1 + 0.16, y1 - fw, y1, z0 - 0.12, z1 + 0.12, edge, G_LIMB,
        skip=("top", "bottom"))
    box(bx0 - 0.12, bx1 + 0.16, y0 + fw, y1 - fw, z0 - 0.12, z0 + 0.24, edge, G_LIMB,
        skip=("top", "bottom"))
    box(bx0 - 0.12, bx1 + 0.16, y0 + fw, y1 - fw, z1 - 0.24, z1 + 0.12, edge, G_LIMB,
        skip=("top", "bottom"))

    if kind == "peg":
        cols = max(4, int((d - 2 * fw) / 3.2))
        rows = max(4, int((h - 2 * fw) / 6.4))
        sz = 1.05
        sy = (h - 2 * fw - 6.0) / max(1, rows - 1)
        szz = (d - 2 * fw - 5.0) / max(1, cols - 1)
        for i in range(rows):
            for j in range(cols):
                hy = y0 + fw + 3.0 + i * sy
                hz = z0 + fw + 2.5 + j * szz
                if hy + sz > y1 - fw or hz + sz > z1 - fw:
                    continue
                quad((bx1 + 0.06, hy, hz + sz), (bx1 + 0.06, hy, hz),
                     (bx1 + 0.06, hy + sz, hz), (bx1 + 0.06, hy + sz, hz + sz),
                     hole, G_LIMB)
    CUR_SLOT = None


RISER_W = (60.0, 76.0)          # 可选宽度
RISER_H = (6.0, 10.0, 14.0)     # 可选高度


def _build_riser(w, hgt):
    """靠墙的增高架：背贴 z≈0，居中放在书架下层内"""
    global CUR_SLOT
    CUR_SLOT = ("riser", "%dx%d" % (int(w), int(hgt)))
    z0, z1 = 1.0, 21.0
    y = 75.0
    x0 = 1.8 + (84.4 - w) / 2.0          # 书架内净宽 84.4，居中
    x1 = x0 + w
    box(x0, x1, y + hgt - 2.0, y + hgt, z0, z1, C_WOOD_L, G_LIMB)          # 台面
    box(x0, x0 + 6.0, y, y + hgt - 2.0, z0, z1, C_WOOD_D, G_LIMB,
        skip=("top", "bottom"))                                          # 左腿板
    box(x1 - 6.0, x1, y, y + hgt - 2.0, z0, z1, C_WOOD_D, G_LIMB,
        skip=("top", "bottom"))                                          # 右腿板
    box(x0 + 6.0, x1 - 6.0, y + hgt - 2.8, y + hgt - 2.0, z1 - 1.2, z1,
        C_WOOD_D, G_LIMB, skip=("top", "bottom"))                        # 前沿挡条
    CUR_SLOT = None


def _build_gp_holder():
    """手柄架：缩小版，底板离板面留 0.2 间隙"""
    global CUR_SLOT
    CUR_SLOT = ("gamepad", "on")
    xb = 87.8
    box(xb - 2.0, xb, 121.0, 127.0, 8.0, 16.0, C_WHITE, G_LIMB)          # 底板 6×8
    for zz in (8.4, 13.6):
        box(81.2, xb - 2.0, 119.5, 121.8, zz, zz + 1.8, C_WHITE, G_LIMB)  # 横爪
        box(81.2, 82.8, 121.8, 126.6, zz, zz + 1.8, C_WHITE, G_LIMB)      # 上翘
    box(81.2, xb - 2.0, 116.5, 119.5, 10.0, 14.0, C_WHITE, G_LIMB)        # 下托
    CUR_SLOT = None


def _build_hp_holder():
    """耳机架：缩小版，钩更短"""
    global CUR_SLOT
    CUR_SLOT = ("headphone", "on")
    xb = 87.8
    box(xb - 2.0, xb, 96.5, 100.5, 9.5, 14.5, C_WHITE, G_LIMB)           # 底板 4×5
    box(83.0, xb - 2.0, 97.2, 99.4, 10.8, 13.2, C_WHITE, G_LIMB)          # 横臂
    box(83.0, 84.4, 99.4, 103.6, 10.8, 13.2, C_WHITE, G_LIMB)             # 上翘钩
    CUR_SLOT = None



def _build_mon():
    """显示器 21.5\"：屏体 52 × 28，坐在桌面上"""
    global CUR_SLOT
    CUR_SLOT = ("mon", "on")
    y = DIMS["DESK_H"]
    sx0, sx1 = 24.0, 76.0
    sy0, sy1 = 80.0, 108.0
    sz0, sz1 = 12.0, 15.0
    box(sx0, sx1, sy0, sy1, sz0, sz1, C_BEZEL, G_LIMB)
    quad((sx0 + 1.2, sy0 + 1.2, sz1), (sx1 - 1.2, sy0 + 1.2, sz1),
         (sx1 - 1.2, sy1 - 1.2, sz1), (sx0 + 1.2, sy1 - 1.2, sz1), C_SCREEN, G_LIMB)
    box(44.0, 56.0, y, y + 1.4, 6.0, 15.0, C_BEZEL, G_LIMB)
    box(48.4, 51.6, y + 1.4, sy0, 8.0, 11.0, C_BEZEL, G_LIMB)
    CUR_SLOT = None


def _build_kb():
    """键盘 + 大桌垫 + 鼠标"""
    global CUR_SLOT
    CUR_SLOT = ("kb", "on")
    y = DIMS["DESK_H"]
    box(30.0, 66.0, y, y + 1.4, 38.0, 50.0, C_KEY, G_LIMB)
    box(30.6, 65.4, y + 1.4, y + 1.9, 38.8, 49.2, (74, 76, 82), G_LIMB)
    box(52.0, 86.0, y, y + 0.3, 34.0, 52.0, C_MAT, G_LIMB)
    box(70.0, 76.0, y + 0.3, y + 2.0, 40.0, 48.0, (64, 66, 72), G_LIMB)
    CUR_SLOT = None


def _build_spk():
    """桌面音箱 ×2：书架下层两个后角"""
    global CUR_SLOT
    CUR_SLOT = ("spk", "on")
    y = DIMS["DESK_H"]
    for _x in (4.0, 76.0):
        box(_x, _x + 6.0, y, y + 9.0, 1.6, 7.6, C_SPK, G_LIMB)
        quad((_x + 0.8, y + 1.6, 7.6), (_x + 5.2, y + 1.6, 7.6),
             (_x + 5.2, y + 7.4, 7.6), (_x + 0.8, y + 7.4, 7.6), (34, 36, 40), G_LIMB)
    CUR_SLOT = None


def _build_plant():
    """绿植：陶盆 + 三片叶"""
    global CUR_SLOT
    CUR_SLOT = ("plant", "on")
    y = DIMS["DESK_H"]
    box(12.0, 18.0, y, y + 5.0, 1.6, 7.6, C_POT, G_LIMB)
    box(14.2, 15.8, y + 5.0, y + 10.0, 4.2, 5.4, (92, 108, 74), G_LIMB)
    quad((15.0, y + 9.0, 4.8), (8.0, y + 11.4, 4.8), (8.0, y + 12.4, 4.8), (15.0, y + 10.4, 4.8),
         C_LEAF, G_LIMB)
    quad((15.0, y + 9.6, 4.8), (22.0, y + 11.8, 4.8), (22.0, y + 12.8, 4.8), (15.0, y + 10.8, 4.8),
         C_LEAF, G_LIMB)
    quad((15.0, y + 10.0, 4.8), (12.0, y + 14.2, 4.8), (13.2, y + 14.8, 4.8), (15.6, y + 10.8, 4.8),
         (78, 110, 70), G_LIMB)
    box(20.0, 25.0, y, y + 8.0, 15.0, 20.0, C_CERAMIC, G_LIMB)
    box(20.6, 24.4, y + 7.4, y + 8.0, 15.6, 19.4, (196, 190, 178), G_LIMB)
    CUR_SLOT = None


def _build_org():
    """桌面收纳抽屉柜：18 宽 × 3 层"""
    global CUR_SLOT
    CUR_SLOT = ("org", "on")
    y = DIMS["DESK_H"]
    box(66.0, 84.0, y, y + 18.0, 1.6, 14.0, C_WOOD_L, G_LIMB)
    for _k in range(3):
        _yy = y + 1.6 + _k * 5.6
        box(66.6, 83.4, _yy, _yy + 4.8, 14.0, 14.6, C_WOOD, G_LIMB)
        box(73.8, 76.2, _yy + 2.2, _yy + 3.0, 14.6, 15.2, (120, 114, 104), G_LIMB)
    CUR_SLOT = None


def _build_books():
    """书架上层：一排书 + 两个收纳盒"""
    global CUR_SLOT
    CUR_SLOT = ("books", "on")
    sy = DIMS["DESK_H"] + DIMS["HUTCH_TIER"] + DIMS["HUTCH_P"]
    BOOKS = [(196, 176, 148), (92, 104, 120), (150, 96, 78), (110, 128, 104),
             (168, 150, 120), (76, 84, 96), (140, 120, 96), (120, 106, 132)]
    _bx = 5.0
    for i in range(9):
        _w = 2.6 + (i % 3) * 0.7
        _h = 17.0 + (i * 7 % 5) * 1.6
        box(_bx, _bx + _w, sy, sy + _h, 2.4, 16.4, BOOKS[i % len(BOOKS)], G_LIMB)
        _bx += _w + 0.5
    for _x in (56.0, 70.0):
        box(_x, _x + 13.0, sy, sy + 11.0, 3.0, 18.0, (208, 200, 186), G_LIMB)
        box(_x + 0.8, _x + 12.2, sy + 4.0, sy + 10.4, 18.0, 18.4, (188, 180, 166), G_LIMB)
    CUR_SLOT = None


def _build_deco():
    """精装件：拆成 6 个独立开关"""
    _build_mon()
    _build_kb()
    _build_spk()
    _build_plant()
    _build_org()
    _build_books()


def build_accessories():
    """可选配件：板材（2 种 × 3 尺寸）+ 层板下的条形灯"""
    global CUR_SLOT
    for kind in ("peg", "felt"):
        for size in ("60", "80"):
            _build_board(kind, size)

    # --- 条形灯：贴在书架中间层板底面，朝下发光 ---
    CUR_SLOT = ("lamp", "shelf")
    lx0, lx1 = 22.0, 66.0
    ly0, ly1 = 124.4, 128.0
    lz0, lz1 = 16.6, 22.2
    box(lx0, lx1, ly0, ly1, lz0, lz1, (198, 200, 204), G_LIMB)
    box(lx0 - 0.7, lx0 + 1.5, ly0 - 0.2, ly1, lz0 - 0.35, lz1 + 0.35,
        (118, 120, 126), G_LIMB)
    box(lx1 - 1.5, lx1 + 0.7, ly0 - 0.2, ly1, lz0 - 0.35, lz1 + 0.35,
        (118, 120, 126), G_LIMB)
    quad((lx0 + 1.6, ly0 - 0.08, lz1 - 0.8), (lx0 + 1.6, ly0 - 0.08, lz0 + 0.8),
         (lx1 - 1.6, ly0 - 0.08, lz0 + 0.8), (lx1 - 1.6, ly0 - 0.08, lz1 - 0.8),
         (255, 249, 228), G_LIMB)
    box(lx0 + 3.0, lx1 - 3.0, ly1 - 0.5, ly1, lz0 + 1.4, lz0 + 2.4,
        (150, 152, 158), G_LIMB)

    _build_gp_holder()
    _build_hp_holder()
    _build_deco()

    # --- 增高架：靠墙放，尺寸可选（宽 × 高）---
    for _w in RISER_W:
        for _h in RISER_H:
            _build_riser(_w, _h)



    # --- 床板下的条形灯：吊在床板底面，照桌面正前方 ---
    CUR_SLOT = ("lamp", "bed")
    kx0, kx1 = 40.0, 84.0
    ky0, ky1 = 182.2, 186.0
    kz0, kz1 = 30.0, 35.6
    box(kx0, kx1, ky0, ky1, kz0, kz1, (198, 200, 204), G_LIMB)
    box(kx0 - 0.7, kx0 + 1.5, ky0, ky1 + 0.2, kz0 - 0.35, kz1 + 0.35,
        (118, 120, 126), G_LIMB)
    box(kx1 - 1.5, kx1 + 0.7, ky0, ky1 + 0.2, kz0 - 0.35, kz1 + 0.35,
        (118, 120, 126), G_LIMB)
    quad((kx0 + 1.6, ky0 - 0.08, kz1 - 0.8), (kx0 + 1.6, ky0 - 0.08, kz0 + 0.8),
         (kx1 - 1.6, ky0 - 0.08, kz0 + 0.8), (kx1 - 1.6, ky0 - 0.08, kz1 - 0.8),
         (255, 249, 228), G_LIMB)
    for px in (kx0 + 4.0, kx1 - 6.0):
        box(px, px + 2.0, ky1 - 0.4, ky1, kz0 + 1.6, kz1 - 1.6,
            (120, 122, 126), G_LIMB)
    CUR_SLOT = None

def build_unit():
    build_bed()
    build_ward()
    build_desk()
    build_column()
    build_drawer()
    build_hutch()
    build_accessories()


def build_all():
    global CUR_DOOR, DOOR_TAG, CUR_UNIT
    FACES.clear()
    FACE_DOOR.clear()
    FACE_META.clear()
    BOXES.clear()
    UNIT_XFORMS.clear()
    CUR_DOOR = None
    CUR_UNIT = -1                 # 环境与共享梯子不属于任何床位
    build_env()

    # sx/sz = ±1（负号表示镜像），ox/oz = 平移；单位 cm
    units = [
        (1, 1, 0.0, 0.0),          # 我的床位
        (-1, 1, -160.0, 0.0),      # 隔壁，与我共用梯子
        (-1, -1, -160.0, 300.0),   # 对面左
        (1, -1, 0.0, 300.0),        # 对面右，与左共用梯子
    ]
    for idx, (sx, sz, ox, oz) in enumerate(units):
        XFORM.update(sx=sx, sz=sz, ox=ox, oz=oz)
        DOOR_TAG = True
        CUR_UNIT = idx
        UNIT_XFORMS.append((sx, sz, ox, oz))
        for _d in DOORS_BASE:
            ALL_DOORS.append({
                "id": str(idx) + "|" + _d["id"], "unit": idx,
                "label": ((("右侧" if sx * sz > 0 else "左侧") + "柜门")
                          if _d["id"] == "cab" else _d["label"]), "kind": _d["kind"],
                "hx": sx * _d.get("hx", 0.0) + ox, "hz": sz * _d.get("hz", 0.0) + oz,
                "sign": _d.get("sign", 1) * (1 if sx * sz > 0 else -1),
                "dz": sz,                     # 平移门的方向：跟着单元 z 翻转走
                "max": _d["max"]})
        build_unit()

    XFORM.update(sx=1, sz=1, ox=0.0, oz=0.0)
    DOOR_TAG = False
    CUR_UNIT = -1
    ytop = DIMS["BED_Y"] + DIMS["BED_T"]
    build_shared_ladder(-80.0, 70.0, 92.0, ytop)       # 我这侧的共享梯
    build_shared_ladder(-80.0, 208.0, 230.0, ytop)     # 对面的共享梯

def export_files():
    bd.FACES = FACES
    bd.ANNOTS = []
    bd.W = DIMS["DESK_W"]
    bd.Dp = DIMS["DESK_D"]
    bd.H = DIMS["DESK_H"]
    bd.SHELF_Y = DIMS["DESK_H"] + DIMS["HUTCH_TIER"]
    bd.BED_Y = DIMS["BED_Y"]
    bd.CAB_W = DIMS["COL_W"]
    bd.CAB_D = DIMS["COL_D"]
    bd.export_obj(os.path.join(ROOT, "宿舍结构模型.obj"),
                  os.path.join(ROOT, "宿舍结构模型.mtl"))
    total, nv, _ = bd.export_glb(os.path.join(ROOT, "宿舍结构模型.glb"))
    print("OBJ / GLB(%.0fKB, %d 顶点) 已导出" % (total / 1024, nv))


def export_html_interactive(path):
    data = []
    for i, (pts, n, color, group) in enumerate(FACES):
        data.append({
            "p": [[round(c[0], 2), round(c[1], 2), round(c[2], 2)] for c in pts],
            "n": [round(x, 3) for x in n],
            "c": [color[0], color[1], color[2]],
            "g": group,
            "d": FACE_DOOR[i],
        })
    groups = []
    for pts, n, color, group in FACES:
        if group != G_ENV and group not in groups:
            groups.append(group)

    html = HTML_TMPL
    for k, v in (("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                 ("__DOORS__", json.dumps(ALL_DOORS, ensure_ascii=False)),
                 ("__GROUPS__", json.dumps(groups, ensure_ascii=False)),
                 ("__W__", "%.0f" % DIMS["DESK_W"]),
                 ("__D__", "%.0f" % DIMS["DESK_D"]),
                 ("__H__", "%.0f" % DIMS["DESK_H"]),
                 ("__FH__", "%.0f" % DIMS["FURN_H"]),
                 ("__NFACE__", str(len(FACES)))):
        html = html.replace(k, v)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


HTML_TMPL = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>宿舍结构模型 · 可旋转 · 可开门</title>
<style>
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;overflow:hidden;background:#f7f2ea;
    font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#2a241e}
  canvas{display:block;width:100vw;height:100vh;cursor:grab;touch-action:none}
  canvas.drag{cursor:grabbing}
  .hud{position:fixed;left:30px;top:26px;pointer-events:none}
  .hud .k{font-size:10.5px;letter-spacing:.22em;color:#b4552d;margin-bottom:7px}
  .hud h1{font-size:21px;margin:0 0 6px;font-weight:700}
  .hud p{margin:0;font-size:12.5px;color:#8b8177;line-height:1.7}
  .spec{position:fixed;left:30px;bottom:24px;font-size:12px;color:#8b8177;
    background:rgba(255,253,248,.9);border:1px solid #e6dccb;border-radius:10px;
    padding:11px 15px;line-height:1.95;pointer-events:none}
  .spec b{color:#2a241e;font-weight:600}
  .panel{position:fixed;right:20px;top:20px;width:218px;background:rgba(255,253,248,.96);
    border:1px solid #e6dccb;border-radius:12px;padding:14px 16px 12px;
    box-shadow:0 8px 26px rgba(120,100,70,.10);font-size:12px;
    max-height:calc(100vh - 40px);overflow-y:auto}
  .panel h2{font-size:10.5px;letter-spacing:.14em;color:#b4552d;margin:0 0 9px;font-weight:600}
  .row{display:flex;align-items:center;gap:7px;margin:6px 0;cursor:pointer;user-select:none}
  .row input{accent-color:#b4552d;cursor:pointer;margin:0;flex:none}
  .row span{color:#4a423a;font-size:11.5px}
  .door{margin:10px 0 12px}
  .door .lab{display:flex;justify-content:space-between;font-size:11.5px;
    color:#4a423a;margin-bottom:5px}
  .door .lab i{font-style:normal;color:#b4552d;font-size:10.5px}
  input[type=range]{width:100%;accent-color:#b4552d;height:16px}
  .sep{height:1px;background:#eee4d4;margin:12px 0}
  .btn{width:100%;border:1px solid #dfd3bf;background:#fffdf8;color:#5a5148;
    font-size:11.5px;padding:7px;border-radius:8px;cursor:pointer;font-family:inherit;margin-top:5px}
  .btn:hover{border-color:#b4552d;color:#b4552d}
  .note{font-size:10.5px;color:#a99e90;line-height:1.6;margin-top:9px}
</style></head>
<body>
<canvas id="c"></canvas>
<div class="hud">
  <div class="k">宿舍家具 · 结构模型</div>
  <h1>上床下桌</h1>
  <p>拖动旋转 · 滚轮缩放 · 双击复位 · 右侧可开门</p>
</div>
<div class="spec">
  桌面 <b>__W__ × __D__</b> cm · 桌高 <b>__H__</b> · 柜体高 <b>__FH__</b><br>
  共 <b>__NFACE__</b> 个面 · 尺寸表驱动
</div>
<div class="panel">
  <h2>开门 / 抽屉</h2>
  <div id="doors"></div>
  <button class="btn" id="allon">全部打开</button>
  <button class="btn" id="alloff">全部关上</button>
  <div class="sep"></div>
  <h2>显示分组</h2>
  <div id="toggles"></div>
  <div class="sep"></div>
  <button class="btn" id="reset">复位视角</button>
  <div class="note">只含家具结构，不含任何物品</div>
</div>
<script>
const FACES = __DATA__;
const DOORS = __DOORS__;
const GROUPS = __GROUPS__;
const cv = document.getElementById('c');
const ctx = cv.getContext('2d');
const DMAP = {}; DOORS.forEach(d => DMAP[d.id] = d);
const state = {}; DOORS.forEach(d => state[d.id] = 0);

let bx=[1e9,-1e9], by=[1e9,-1e9], bz=[1e9,-1e9];
for(const f of FACES){
  if(f.g==='环境') continue;
  for(const p of f.p){
    if(p[0]<bx[0])bx[0]=p[0]; if(p[0]>bx[1])bx[1]=p[0];
    if(p[1]<by[0])by[0]=p[1]; if(p[1]>by[1])by[1]=p[1];
    if(p[2]<bz[0])bz[0]=p[2]; if(p[2]>bz[1])bz[1]=p[2];
  }
}
const CEN=[(bx[0]+bx[1])/2,(by[0]+by[1])/2,(bz[0]+bz[1])/2];
const RAD=0.5*Math.hypot(bx[1]-bx[0], by[1]-by[0], bz[1]-bz[0]);

let yaw=-0.62, pitch=0.30, zoom=1.0, panX=0, panY=0;
const DEF={yaw:-0.62,pitch:0.30,zoom:1.0};
const hidden=new Set();
const LV=[-0.42,0.80,0.43], LL=Math.hypot(...LV), LIGHT=LV.map(x=>x/LL);

const TMP={p:null,n:null};
function applyDoor(f){
  const id=f.d;
  if(!id || (state[id]||0) < 0.002){ TMP.p=f.p; TMP.n=f.n; return; }
  const d=DMAP[id], st=state[id];
  if(d.kind==='swing'){
    const a=d.sign*st*d.max*Math.PI/180;
    const c=Math.cos(a), s=Math.sin(a);
    TMP.p=f.p.map(p=>{
      const dx=p[0]-d.hx, dz=p[2]-d.hz;
      return [d.hx+dx*c-dz*s, p[1], d.hz+dx*s+dz*c];
    });
    TMP.n=[f.n[0]*c-f.n[2]*s, f.n[1], f.n[0]*s+f.n[2]*c];
  }else{
    const off=st*d.max;
    TMP.p=f.p.map(p=>[p[0], p[1], p[2]+off]);
    TMP.n=f.n;
  }
}

function resize(){
  const dpr=Math.min(window.devicePixelRatio||1,2);
  cv.width=Math.max(1,Math.round(innerWidth*dpr));
  cv.height=Math.max(1,Math.round(innerHeight*dpr));
  ctx.setTransform(dpr,0,0,dpr,0,0);
  draw();
}

function draw(){
  const w=innerWidth, h=innerHeight;
  const g=ctx.createRadialGradient(w*0.5,h*0.42,40,w*0.5,h*0.5,Math.max(w,h)*0.78);
  g.addColorStop(0,'#fffdf8'); g.addColorStop(0.55,'#f8f1e5'); g.addColorStop(1,'#ebe0cf');
  ctx.fillStyle=g; ctx.fillRect(0,0,w,h);

  const camD=Math.max(3.0*RAD/zoom, 1.25*RAD);   // 放大时相机凑近，透视变强；有下限防止钻进模型
  const focal=0.44*Math.min(w,h)*(camD/RAD)*zoom;
  const cy=Math.cos(yaw), sy=Math.sin(yaw);
  const cp=Math.cos(pitch), sp=Math.sin(pitch);

  const list=[];
  for(const f of FACES){
    if(hidden.has(f.g)) continue;
    applyDoor(f);
    const pr=[]; let zs=0;
    for(const p of TMP.p){
      const x=p[0]-CEN[0], y=p[1]-CEN[1], z=p[2]-CEN[2];
      const x1=x*cy + z*sy, z1=-x*sy + z*cy;
      const y2=y*cp - z1*sp, z2=y*sp + z1*cp;
      zs+=z2; pr.push([x1,y2,z2]);
    }
    const depth=camD - zs/4;
    if(depth<8) continue;
    list.push({c:f.c, n:TMP.n, pr:pr, s:focal/depth, depth:depth});
  }
  list.sort((a,b)=>b.depth-a.depth);

  for(const it of list){
    const s=it.s, n=it.n;
    const lam=Math.max(0,n[0]*LIGHT[0]+n[1]*LIGHT[1]+n[2]*LIGHT[2]);
    const sh=0.46+0.62*lam;
    const r=Math.min(255,it.c[0]*sh)|0, g2=Math.min(255,it.c[1]*sh)|0, b=Math.min(255,it.c[2]*sh)|0;
    ctx.beginPath();
    for(let i=0;i<4;i++){
      const p=it.pr[i];
      const X=w/2+panX+p[0]*s, Y=h/2+panY-p[1]*s;
      if(i===0) ctx.moveTo(X,Y); else ctx.lineTo(X,Y);
    }
    ctx.closePath();
    ctx.fillStyle='rgb('+r+','+g2+','+b+')'; ctx.fill();
    ctx.strokeStyle='rgb('+((r*0.88)|0)+','+((g2*0.88)|0)+','+((b*0.88)|0)+')';
    ctx.lineWidth=0.6; ctx.stroke();
  }
}

let drag=false, lx=0, ly=0;
cv.addEventListener('pointerdown',e=>{drag=true;lx=e.clientX;ly=e.clientY;cv.classList.add('drag');});
addEventListener('pointerup',()=>{drag=false;cv.classList.remove('drag');});
addEventListener('pointermove',e=>{
  if(!drag) return;
  yaw+=(e.clientX-lx)*0.008;
  pitch+=(e.clientY-ly)*0.006;
  pitch=Math.max(-0.95,Math.min(1.15,pitch));
  lx=e.clientX; ly=e.clientY; draw();
});
cv.addEventListener('wheel',e=>{
  e.preventDefault();
  const mx=e.clientX, my=e.clientY;
  const nz=Math.max(0.35,Math.min(8.0, zoom*(e.deltaY>0?0.90:1.1111)));
  const kk=nz/zoom;
  panX = mx-innerWidth/2  - (mx-innerWidth/2  - panX)*kk;
  panY = my-innerHeight/2 - (my-innerHeight/2 - panY)*kk;
  const lim=Math.max(innerWidth,innerHeight)*2;
  panX=Math.max(-lim,Math.min(lim,panX)); panY=Math.max(-lim,Math.min(lim,panY));
  zoom=nz; draw();
},{passive:false});
cv.addEventListener('dblclick',()=>{yaw=DEF.yaw;pitch=DEF.pitch;zoom=DEF.zoom;panX=0;panY=0;draw();});

const dbox=document.getElementById('doors');
const sliders={};
DOORS.forEach(d=>{
  const wrap=document.createElement('div'); wrap.className='door';
  const lab=document.createElement('div'); lab.className='lab';
  const nm=document.createElement('span'); nm.textContent=d.label;
  const val=document.createElement('i'); val.textContent='关';
  lab.appendChild(nm); lab.appendChild(val);
  const sl=document.createElement('input');
  sl.type='range'; sl.min=0; sl.max=100; sl.value=0;
  sl.addEventListener('input',()=>{
    state[d.id]=sl.value/100;
    val.textContent = sl.value==0 ? '关'
      : (d.kind==='slide' ? Math.round(d.max*sl.value/100)+' cm'
                          : Math.round(d.max*sl.value/100)+'°');
    draw();
  });
  wrap.appendChild(lab); wrap.appendChild(sl);
  dbox.appendChild(wrap);
  sliders[d.id]=sl;
});
document.getElementById('allon').onclick=()=>{
  DOORS.forEach(d=>{ sliders[d.id].value=100;
    sliders[d.id].dispatchEvent(new Event('input')); });
};
document.getElementById('alloff').onclick=()=>{
  DOORS.forEach(d=>{ sliders[d.id].value=0;
    sliders[d.id].dispatchEvent(new Event('input')); });
};

const tbox=document.getElementById('toggles');
for(const name of GROUPS){
  const row=document.createElement('label'); row.className='row';
  const ck=document.createElement('input'); ck.type='checkbox'; ck.checked=true;
  ck.addEventListener('change',()=>{ if(ck.checked) hidden.delete(name); else hidden.add(name); draw(); });
  row.appendChild(ck);
  const sp=document.createElement('span'); sp.textContent=name; row.appendChild(sp);
  tbox.appendChild(row);
}
document.getElementById('reset').onclick=()=>{yaw=DEF.yaw;pitch=DEF.pitch;zoom=DEF.zoom;panX=0;panY=0;draw();};
addEventListener('resize',resize);
resize();
</script>
</body></html>
"""


def render_stills():
    import render_pro as rp
    rp.bd = sys.modules[__name__]
    rp.WOOD_COLORS |= {C_WOOD, C_WOOD_D, C_WOOD_L}
    rp.METAL_COLORS |= {C_STEEL, C_STEEL_L}
    bd.ANNOTS = []

    views = [
        ("结构_01_俯视.png", 0.0, 1.5707, 1.00, (), None, True),
        ("结构_02_全景.png", -0.35, 0.55, 1.00, (), None, False),
        ("结构_03_我的床位.png", -0.62, 0.34, 1.00, (), ((28.0, 110.0, 46.0), 128.0), False),
        ("结构_04_桌面细节.png", -0.72, 0.34, 1.00,
         (G_WARD, G_BED, G_STAIR), ((62.0, 95.0, 20.0), 78.0), False),
    ]
    for name, yw, pt, zm, hide, focus, ortho in views:
        rp.render_pro(os.path.join(ROOT, name), yw, pt, zoom=zm, hide=hide,
                      focus=focus, ortho=ortho, show_annot=False, ss=2,
                      stage=(), use_shadow=False)
        print("出图:", name)

if __name__ == "__main__":
    build_all()
    print("面数:", len(FACES), " 门:", len(DOORS))
    export_files()
    export_html_interactive(os.path.join(ROOT, "宿舍结构模型_可旋转.html"))
    print("HTML 已导出")
    render_stills()

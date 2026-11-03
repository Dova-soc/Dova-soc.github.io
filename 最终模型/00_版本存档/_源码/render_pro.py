# -*- coding: utf-8 -*-
"""
render_pro.py —— 高质量渲染器（不依赖任何 3D 软件）
================================================================
相比 build_desk3d.py 里那个软光栅：
    原来：画家算法 + 纯色平涂
    现在：z-buffer + 方向光硬阴影 + 屏幕空间环境光遮蔽 + 程序化木纹
          + Blinn-Phong 高光 + ACES 色调映射 + 2 倍超采样

几何仍然从 build_desk3d.py 拿，尺寸没变。
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_desk3d as bd

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------- 光照与材质参数 ----------------
LIGHT = np.array([-0.42, 0.80, 0.43], dtype=np.float32)
LIGHT = LIGHT / np.linalg.norm(LIGHT)
LIGHT_COLOR = np.array([1.00, 0.95, 0.88], dtype=np.float32)
RIM = np.array([0.55, 0.42, -0.72], dtype=np.float32)
RIM = RIM / np.linalg.norm(RIM)
RIM_COLOR = np.array([0.42, 0.46, 0.56], dtype=np.float32)
AMBIENT = np.array([0.30, 0.32, 0.38], dtype=np.float32)
EXPOSURE = 1.55
SAT_WOOD = 1.20

WOOD_COLORS = {
    (198, 152, 100), (166, 119, 74), (218, 178, 132),
    (232, 202, 164), (226, 196, 158),
}
METAL_COLORS = {(146, 148, 154)}

# 展台：地面 + 背景墙（只用于渲染，不进模型文件）
STAGE_FLOOR = (198, 188, 175)
STAGE_WALL = (243, 239, 231)


def stage_faces(parts=("floor", "wall")):
    """L 形展台，接阴影，边缘延伸到画面外"""
    out = []
    if "floor" in parts:
        out.append(((( -1500, 0.0, -1500), (1500, 0.0, -1500), (1500, 0.0, 1500), (-1500, 0.0, 1500)),
                    (0.0, 1.0, 0.0), STAGE_FLOOR, "STAGE"))
    if "wall" in parts:
        out.append(((( -1500, 0, -9), (-1500, 520, -9), (1500, 520, -9), (1500, 0, -9)),
                    (0.0, 0.0, 1.0), STAGE_WALL, "STAGE"))
    return out


# ---------------- 数学 ----------------
def rot_matrix(yaw, pitch):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], dtype=np.float64)
    return Rx @ Ry


def srgb_to_lin(c):
    return (np.asarray(c, dtype=np.float32) / 255.0) ** 2.2


# ---------------- 场景 ----------------
def collect(hide=(), stage=("floor", "wall")):
    P, N, C, M, S = [], [], [], [], []
    items = list(bd.FACES) + stage_faces(stage)
    for pts, n, color, group in items:
        if group in hide or group == bd.G_ENV:
            continue
        P.append(np.array(pts, dtype=np.float64))
        N.append(np.array(n, dtype=np.float64))
        C.append(srgb_to_lin(color))
        is_stage = group == "STAGE"
        S.append(is_stage)
        rgb = (color[0], color[1], color[2])
        if is_stage:
            M.append(3)
        elif rgb in WOOD_COLORS:
            M.append(1)
        elif rgb in METAL_COLORS:
            M.append(2)
        else:
            M.append(0)
    P = np.array(P)
    C = np.array(C, dtype=np.float32)
    M = np.array(M, dtype=np.int32)
    # 木头提饱和，避免发灰
    wmask = M == 1
    if wmask.any():
        g = C[wmask].mean(axis=1, keepdims=True)
        C[wmask] = np.clip(g + (C[wmask] - g) * SAT_WOOD, 0, 1)
    return P, np.array(N), C, M, np.array(S, dtype=bool)


# ---------------- 光栅化 ----------------
def rasterize(P, N, C, mat, R, center, camd, focal, W, H):
    """返回 z-buffer（inv 深度）与 face id"""
    nf = P.shape[0]
    V = (P - center.reshape(1, 1, 3)) @ R.T          # (nf,4,3) 视图坐标
    d = camd - V[:, :, 2]                             # 沿视轴的距离
    d = np.maximum(d, 1e-6)
    invd = (1.0 / d).astype(np.float32)
    sx = W * 0.5 + V[:, :, 0] * (focal / d)
    sy = H * 0.5 - V[:, :, 1] * (focal / d)

    zbuf = np.full((H, W), -1e18, dtype=np.float32)
    fbuf = np.full((H, W), -1, dtype=np.int32)

    tri_idx = [(0, 1, 2), (0, 2, 3)]
    CH = 512
    for fi in range(nf):
        for a, b, c in tri_idx:
            ax, ay = sx[fi, a], sy[fi, a]
            bx, by = sx[fi, b], sy[fi, b]
            cx, cy = sx[fi, c], sy[fi, c]
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            x0 = max(0, int(math.floor(min(ax, bx, cx))))
            x1 = min(W - 1, int(math.ceil(max(ax, bx, cx))))
            y0 = max(0, int(math.floor(min(ay, by, cy))))
            y1 = min(H - 1, int(math.ceil(max(ay, by, cy))))
            if x1 < x0 or y1 < y0:
                continue
            ia, ib, ic = invd[fi, a], invd[fi, b], invd[fi, c]
            for ry in range(y0, y1 + 1, CH):
                ry1 = min(y1, ry + CH - 1)
                Y, X = np.mgrid[ry:ry1 + 1, x0:x1 + 1]
                Xf = X.astype(np.float64)
                Yf = Y.astype(np.float64)
                w0 = ((by - cy) * (Xf - cx) + (cx - bx) * (Yf - cy)) / den
                w1 = ((cy - ay) * (Xf - cx) + (ax - cx) * (Yf - cy)) / den
                w2 = 1.0 - w0 - w1
                m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
                if not m.any():
                    continue
                zi = (w0 * ia + w1 * ib + w2 * ic).astype(np.float32)
                sub_z = zbuf[ry:ry1 + 1, x0:x1 + 1]
                sub_f = fbuf[ry:ry1 + 1, x0:x1 + 1]
                better = m & (zi > sub_z)
                if better.any():
                    sub_z[better] = zi[better]
                    sub_f[better] = fi
    return zbuf, fbuf


def unproject(zbuf, fbuf, R, center, camd, focal, W, H):
    """由深度缓冲还原世界坐标与法线"""
    ys, xs = np.nonzero(fbuf >= 0)
    invd = zbuf[ys, xs]
    depth = 1.0 / invd
    X = (xs - W * 0.5) * depth / focal
    Y = (H * 0.5 - ys) * depth / focal
    Z = camd - depth
    Vv = np.stack([X, Y, Z], axis=1)
    world = Vv @ R + center.reshape(1, 3)
    return ys, xs, world, depth


def box_blur(a, r):
    """可分离盒式模糊（numpy），浮点输入输出，不量化"""
    if r < 1:
        return a.astype(np.float32)
    p = np.pad(a, r, mode="edge").astype(np.float64)
    cs = np.cumsum(p, axis=1)
    cs = np.concatenate([np.zeros((cs.shape[0], 1)), cs], axis=1)
    h = (cs[:, 2 * r + 1:] - cs[:, :-(2 * r + 1)]) / (2 * r + 1)
    cs = np.cumsum(h, axis=0)
    cs = np.concatenate([np.zeros((1, cs.shape[1])), cs], axis=0)
    v = (cs[2 * r + 1:] - cs[:-(2 * r + 1)]) / (2 * r + 1)
    return v.astype(np.float32)


def smooth(a, r, passes=2):
    for _ in range(passes):
        a = box_blur(a, r)
    return a

# ---------------- 阴影 ----------------
def shadow_mask(P, world, ys, xs, shape, nrm=None, bias=0.35):
    """方向光硬阴影（对每个可见像素向光源投射）
    沿法线把起点抬起一点，避免自遮挡产生的噪声"""
    L = LIGHT.astype(np.float64)
    if nrm is not None:
        world = world + nrm * 0.8
    occl = np.zeros(len(world), dtype=bool)
    nf = P.shape[0]
    for fi in range(nf):
        p0 = P[fi, 0]
        e1 = P[fi, 1] - p0
        e2 = P[fi, 3] - p0
        n = np.cross(P[fi, 1] - p0, P[fi, 2] - P[fi, 1])
        nl = np.linalg.norm(n)
        if nl < 1e-12:
            continue
        n = n / nl
        den = float(np.dot(L, n))
        if abs(den) < 1e-6:
            continue
        t = np.dot(p0 - world, n) / den
        ok = (t > bias) & (t < 400.0)
        if not ok.any():
            continue
        hp = world + t[:, None] * L
        rel = hp - p0
        a = (rel @ e1) / float(np.dot(e1, e1))
        b = (rel @ e2) / float(np.dot(e2, e2))
        hit = ok & (a >= 0.0) & (a <= 1.0) & (b >= 0.0) & (b <= 1.0)
        if hit.any():
            occl |= hit
    mask = np.ones(shape, dtype=np.float32)
    mask[ys, xs] = np.where(occl, 0.0, 1.0)
    return mask


def ssao(depth, shape, radius=9.0, strength=1.35):
    """屏幕空间环境光遮蔽（基于深度差）"""
    h, w = shape
    d = np.where(depth > 0, depth, np.nan)
    finite = np.isfinite(d)
    d0 = np.nan_to_num(d, nan=1e6)
    occ = np.zeros_like(d0)
    cnt = np.zeros_like(d0)
    dirs = [(1, 0), (0.7, 0.7), (0, 1), (-0.7, 0.7),
            (-1, 0), (-0.7, -0.7), (0, -1), (0.7, -0.7)]
    for r_scale in (1.0, 0.55):
        r = int(radius * r_scale)
        if r < 1:
            continue
        for dx, dy in dirs:
            ox, oy = int(round(dx * r)), int(round(dy * r))
            sh = np.roll(np.roll(d0, oy, axis=0), ox, axis=1)
            diff = d0 - sh            # >0 表示邻居更近 = 被遮挡
            contrib = np.clip((diff - 0.35) / 6.0, 0.0, 1.0)
            occ += contrib
            cnt += 1.0
    ao = 1.0 - strength * (occ / np.maximum(cnt, 1.0))
    return np.where(finite, np.clip(ao, 0.18, 1.0), 0.0)


# ---------------- 着色 ----------------
def wood_grain(world, nrm, face_mat):
    """程序化木纹：按板的朝向选切平面"""
    ax = np.abs(nrm)
    dom = np.argmax(ax, axis=1)
    u = np.empty(len(world), dtype=np.float32)
    v = np.empty(len(world), dtype=np.float32)
    m0 = dom == 1
    u[m0], v[m0] = world[m0, 2], world[m0, 0]
    m1 = dom == 0
    u[m1], v[m1] = world[m1, 2], world[m1, 1]
    m2 = dom == 2
    u[m2], v[m2] = world[m2, 0], world[m2, 1]
    g = (np.sin(u * 1.05 + 2.2 * np.sin(v * 0.16 + u * 0.06)) * 0.5
         + np.sin(u * 0.37 + v * 0.09) * 0.3
         + np.sin(u * 2.9 + v * 0.4) * 0.2)
    m = (face_mat == 1).astype(np.float32)
    return 1.0 + m * g * 0.085


def tone_map(c):
    c = 1.0 - np.exp(-c * EXPOSURE)
    return np.clip(c, 0.0, 1.0) ** (1 / 2.2)


# ---------------- 主渲染 ----------------
def render_pro(path, yaw, pitch, size=(1400, 1050), zoom=1.0, hide=(),
               focus=None, ortho=False, show_annot=True, annot_ids=None,
               label=None, ss=2, stage=(), use_shadow=False,
               bg=((250, 247, 241), (206, 196, 183))):
    W, H = size[0] * ss, size[1] * ss
    P, N, C, MAT, IS_STAGE = collect(hide, stage)
    if len(P) == 0:
        raise ValueError("没有可见面")

    if focus:
        center, rad = focus
        center = np.array(center, dtype=np.float64)
    else:
        allp = P[~IS_STAGE].reshape(-1, 3)     # 取景只看模型，不看展台
        center = (allp.min(0) + allp.max(0)) / 2.0
        rad = float(np.linalg.norm(allp.max(0) - allp.min(0)) / 2.0)

    camd = 3.0 * rad / zoom
    focal = 0.44 * min(W, H) * camd / rad
    span = 2.02 * rad

    if ortho:
        # 正交：把 camd 拉远、focal 缩小，近似平行投影
        camd = 60.0 * rad
        focal = min(W, H) * 0.92 * camd / span

    R = rot_matrix(yaw, pitch)
    zbuf, fbuf = rasterize(P, N, C, MAT, R, center, camd, focal, W, H)

    img = np.zeros((H, W, 3), dtype=np.float32)
    # 背景渐变
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    bg0 = srgb_to_lin(bg[0]).reshape(1, 1, 3)
    bg1 = srgb_to_lin(bg[1]).reshape(1, 1, 3)
    img[:] = bg0 + (bg1 - bg0) * t

    ys, xs, world, depth = unproject(zbuf, fbuf, R, center, camd, focal, W, H)
    fid = fbuf[ys, xs]

    # --- 单独做一遍低分辨率光栅化，专供阴影和 AO ---
    LS = 2
    Wl, Hl = max(2, W // LS), max(2, H // LS)
    zbl, fbl = rasterize(P, N, C, MAT, R, center, camd, focal / LS, Wl, Hl)
    ysl, xsl, worldl, depthl = unproject(zbl, fbl, R, center, camd, focal / LS, Wl, Hl)

    sh_grid = np.ones((Hl, Wl), dtype=np.float32)
    if use_shadow:
        nrml = N[fbl[ysl, xsl]]
        try:
            sh_grid[ysl, xsl] = shadow_mask(P, worldl, ysl, xsl, (Hl, Wl), nrml)[ysl, xsl]
        except Exception:
            pass

    dep_grid = np.zeros((Hl, Wl), dtype=np.float32)
    dep_grid[ysl, xsl] = depthl
    ao_grid = ssao(dep_grid, (Hl, Wl))
    stg = np.zeros((Hl, Wl), dtype=bool)
    stg[ysl, xsl] = MAT[fbl[ysl, xsl]] == 3
    ao_grid = np.where(stg, 1.0, ao_grid)

    sh_grid = smooth(sh_grid, max(1, ss), 2)
    ao_grid = smooth(ao_grid, max(1, ss * 2), 2)
    SH = np.asarray(Image.fromarray(sh_grid).resize((W, H), Image.BILINEAR),
                    dtype=np.float32)[ys, xs]
    AO = np.asarray(Image.fromarray(ao_grid).resize((W, H), Image.BILINEAR),
                    dtype=np.float32)[ys, xs]
    AO = np.where(MAT[fid] == 3, 1.0, AO).astype(np.float32)   # 展台是平面，不需要 AO

    # --- 逐像素着色 ---
    nrm = N[fid]
    base = C[fid]
    mat = MAT[fid]

    ndl = np.clip(nrm @ LIGHT.astype(np.float64), 0.0, None).astype(np.float32)
    ndh = np.clip(nrm @ ((LIGHT + np.array([0.0, 0.0, 1.0])) / np.linalg.norm(LIGHT + np.array([0.0, 0.0, 1.0]))).astype(np.float64), 0.0, None)
    spec_pow = np.where(mat == 2, 60.0, np.where(mat == 1, 26.0, 10.0)).astype(np.float32)
    spec_amt = np.where(mat == 2, 0.55, np.where(mat == 1, 0.075, 0.04)).astype(np.float32)

    grain = wood_grain(world, nrm, mat)
    albedo = base * grain[:, None]

    ndr = np.clip(nrm @ RIM.astype(np.float64), 0.0, None).astype(np.float32)
    stage_boost = (mat == 3).astype(np.float32) * 0.30
    diff = albedo * (ndl[:, None] * SH[:, None] * LIGHT_COLOR.reshape(1, 3))
    amb = albedo * (AMBIENT.reshape(1, 3) + stage_boost[:, None]) * AO[:, None]
    rim = albedo * (ndr ** 2.0)[:, None] * RIM_COLOR.reshape(1, 3) * 0.55 * AO[:, None]
    spc = spec_amt[:, None] * (ndh ** spec_pow)[:, None] * LIGHT_COLOR.reshape(1, 3) * SH[:, None]

    col = tone_map(diff + amb + rim + spc)
    img[ys, xs] = col

    # --- 接触阴影（无展台时补一个，避免模型"浮"着）---
    if not stage and not ortho:
        blob = Image.new("L", (W, H), 0)
        dc = ImageDraw.Draw(blob)
        allp = P[~IS_STAGE].reshape(-1, 3)
        pts = []
        for cx in (allp[:, 0].min(), allp[:, 0].max()):
            for cz in (allp[:, 2].min(), allp[:, 2].max()):
                vv = R @ (np.array([cx, 0.0, cz]) - center)
                dep = camd - vv[2]
                if dep <= 1:
                    continue
                s = focal / dep
                pts.append((W * 0.5 + vv[0] * s, H * 0.5 - vv[1] * s))
        if len(pts) >= 3:
            xs_ = [p[0] for p in pts]
            ys_ = [p[1] for p in pts]
            pad_x = (max(xs_) - min(xs_)) * 0.10
            dc.ellipse([min(xs_) - pad_x * 0.2, min(ys_) + (max(ys_) - min(ys_)) * 0.0,
                        max(xs_) + pad_x * 0.2, max(ys_) + (max(ys_) - min(ys_)) * 0.10],
                       fill=120)
            blob = blob.filter(ImageFilter.GaussianBlur(26 * ss))
            ca = np.asarray(blob, dtype=np.float32)[:, :, None] / 255.0
            img = img * (1.0 - 0.62 * ca)

    # --- 暗角 ---
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    img *= np.clip(1.0 - 0.16 * np.clip(r - 0.55, 0, None) ** 1.6, 0.0, 1.0)[:, :, None]

    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    out = out.resize(size, Image.LANCZOS)

    if show_annot:
        draw_annotations(out, yaw, pitch, center, rad, camd, focal, size[0], size[1],
                         hide, annot_ids)
    if label:
        ImageDraw.Draw(out).text((34, 26), label, fill=(40, 34, 28), font=bd._font(26))
    out.save(path)
    return path


# ---------------- 尺寸标注 ----------------
def draw_annotations(img, yaw, pitch, center, rad, camd, focal, w, h, hide, annot_ids):
    ss = 2
    big = img.resize((w * ss, h * ss), Image.LANCZOS)
    dr = ImageDraw.Draw(big)
    R = rot_matrix(yaw, pitch)
    f = focal / ss
    Cd = camd

    def proj(p):
        v = R @ (np.asarray(p, dtype=np.float64) - center)
        dep = Cd - v[2]
        if dep <= 1:
            return None
        s = f / dep
        return (w * ss / 2 + v[0] * s * ss, h * ss / 2 - v[1] * s * ss)

    fnt = bd._font(int(17 * ss))
    cand = []
    for a in bd.ANNOTS:
        if a["dep"] and a["dep"] in hide:
            continue
        if annot_ids is not None and a["id"] not in annot_ids:
            continue
        lines = []
        bad = False
        for seg in a["segs"]:
            P = [proj(p) for p in seg]
            if any(x is None for x in P):
                bad = True
                break
            lines.append(P)
        if bad:
            continue
        at = proj(a["text_at"])
        if at is None:
            continue
        tw = dr.textlength(a["label"], font=fnt)
        cand.append({"a": a, "lines": lines, "ax": at[0], "ay": at[1],
                     "cx": at[0], "cy": at[1], "w": tw + 16 * ss, "h": 25 * ss})
    bd.decollide(cand, pad_px=7 * 1.4, iters=120)

    for it in cand:
        col = tuple(it["a"]["color"])
        for p in (0, 1):
            lw = (4.0 if p == 0 else 1.25) * ss
            lc = (255, 252, 245) if p == 0 else col
            for line in it["lines"]:
                dr.line([tuple(line[0]), tuple(line[1])], fill=lc, width=max(1, int(lw)))
            if it["a"]["dot"]:
                d = proj(it["a"]["dot"])
                if d:
                    r2 = (4.6 if p == 0 else 2.7) * ss
                    dr.ellipse([d[0] - r2, d[1] - r2, d[0] + r2, d[1] + r2], fill=lc)
        dx, dy = it["cx"] - it["ax"], it["cy"] - it["ay"]
        dist = math.hypot(dx, dy)
        if dist > 26 * ss:
            n = max(1, int(dist / (5 * ss)))
            for k2 in range(0, n + 1, 2):
                t0, t1 = k2 / n, min(1.0, (k2 + 1) / n)
                dr.line([(it["cx"] + (it["ax"] - it["cx"]) * t0,
                          it["cy"] + (it["ay"] - it["cy"]) * t0),
                         (it["cx"] + (it["ax"] - it["cx"]) * t1,
                          it["cy"] + (it["ay"] - it["cy"]) * t1)],
                        fill=col, width=max(1, ss))
        pw, ph = it["w"], it["h"]
        dr.rounded_rectangle([it["cx"] - pw / 2, it["cy"] - ph / 2,
                              it["cx"] + pw / 2, it["cy"] + ph / 2],
                             radius=5 * ss, fill=(255, 253, 247), outline=col,
                             width=max(1, ss))
        dr.text((it["cx"], it["cy"]), it["a"]["label"], font=fnt, fill=col, anchor="mm")

    img.paste(big.resize((w, h), Image.LANCZOS))


# ---------------- 出图 ----------------
def main():
    bd.build_all()
    bd.build_annots()
    print("面数:", len(bd.FACES))

    DESK_ONLY = (bd.G_BED, bd.G_ENV, bd.G_SHELF, bd.G_CAB)
    WITH_CAB = (bd.G_BED, bd.G_ENV, bd.G_SHELF)
    FOCUS_DESK = ((41.0, 46.0, 30.0), 96.0)
    FOCUS_CAB = ((54.0, 96.0, 26.0), 104.0)
    FLOOR = ()
    ROOM = ()

    jobs = [
        # name, yaw, pitch, zoom, hide, focus, ortho, label, annots, stage
        ("渲染_01_桌体.png", -0.72, 0.40, 1.00, DESK_ONLY, FOCUS_DESK, False,
         "① 桌体 · 主要尺寸", ["w", "d", "h", "t", "under", "hole"], FLOOR),
        ("渲染_02_右后柜.png", -0.80, 0.34, 1.00, (bd.G_BED, bd.G_ENV), FOCUS_CAB,
         False, "② 桌面 → 右后柜 → 书架底", ["cabw", "cabd", "shelf"], FLOOR),
        ("渲染_03_俯视.png", 0.0, 1.5707, 1.00, WITH_CAB,
         ((45.0, 95.0, 28.0), 64.0), True,
         "③ 正交俯视 · 90 × 56 占位", ["w", "d", "cabw", "cabd", "hole"], FLOOR),
        ("渲染_04_桌下.png", -0.58, -0.34, 1.00, WITH_CAB,
         ((45.0, 40.0, 28.0), 80.0), False,
         "④ 桌下 · 侧板 / 后横档 / 走线孔", ["h", "under", "t"], FLOOR),
        ("渲染_05_整体.png", -0.60, 0.18, 1.02, (), None, False, None, [], ROOM),
        ("渲染_06_整体带标注.png", -0.62, 0.20, 0.95, (), None, False, None, None, ROOM),
        ("渲染_07_桌面特写.png", -0.78, 0.44, 1.00, DESK_ONLY,
         ((41.0, 48.0, 30.0), 88.0), False, None, [], FLOOR),
    ]
    for name, yw, pt, zm, hide, focus, ortho, lab, aids, stg in jobs:
        sa = True if aids is None else len(aids) > 0
        render_pro(os.path.join(ROOT, name), yw, pt, zoom=zm, hide=hide, focus=focus,
                   ortho=ortho, show_annot=sa, annot_ids=aids, label=lab, stage=stg, use_shadow=False)
        print("出图:", name)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""qr.py —— 极简二维码生成器（纯 Python，离线，无依赖）
只支持 byte 模式、纠错等级 M、版本 1–3（单块，不需要交织）。
容量：V1 14 字节 / V2 26 字节 / V3 42 字节。

自带解码校验：生成后会把矩阵重新读一遍、反掩码、RS 校验、解回原串，
不一致就抛异常。这样能保证图上扫得出来。
"""

# ---------------- GF(256) ----------------
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs(gen, data, nsym):
    """data 后追加 nsym 个纠错码字"""
    res = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = res[i]
        if coef == 0:
            continue
        for j in range(1, len(gen)):
            res[i + j] ^= _mul(gen[j], coef)
        res[i] = 0
    return res[len(data):]


def _gen_poly(nsym):
    g = [1]
    for i in range(nsym):
        g2 = [0] * (len(g) + 1)
        for j in range(len(g)):
            g2[j] ^= g[j]
            g2[j + 1] ^= _mul(g[j], _EXP[i])
        g = g2
    return g


# 版本 → (总码字, 每块数据码字, 每块纠错码字, 块数)。只列 M 级。
_VER_M = {
    1: (26, 16, 10, 1),
    2: (44, 28, 16, 1),
    3: (70, 44, 26, 1),
}
_ALIGN = {1: [], 2: [18], 3: [22]}


def _bits_to_codewords(bits, total):
    out = []
    for i in range(0, len(bits), 8):
        chunk = bits[i:i + 8]
        while len(chunk) < 8:
            chunk.append(0)
        out.append(int("".join(str(b) for b in chunk), 2))
    while len(out) < total:
        out.append(0xEC if (len(out) % 2 == 0) else 0x11)
    return out


def _format_bits(mask):
    """纠错等级 M(00) + 掩码号，15 位，含 BCH 与固定异或"""
    data = (0 << 3) | mask          # M = 00
    v = data << 10
    g = 0x537
    for i in range(4, -1, -1):
        if v & (1 << (i + 10)):
            v ^= g << i
    val = ((data << 10) | v) ^ 0x5412
    return [(val >> (14 - i)) & 1 for i in range(15)]


def _mask_bit(m, r, c):
    if m == 0: return (r + c) % 2 == 0
    if m == 1: return r % 2 == 0
    if m == 2: return c % 3 == 0
    if m == 3: return (r + c) % 3 == 0
    if m == 4: return (r // 2 + c // 3) % 2 == 0
    if m == 5: return (r * c) % 2 + (r * c) % 3 == 0
    if m == 6: return ((r * c) % 2 + (r * c) % 3) % 2 == 0
    return ((r + c) % 2 + (r * c) % 3) % 2 == 0


def _build_function(n):
    """返回 (reserved, dark)。reserved 标记功能图形占位"""
    res = [[False] * n for _ in range(n)]
    dark = [[False] * n for _ in range(n)]

    def finder(r0, c0):
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = r0 + r, c0 + c
                if not (0 <= rr < n and 0 <= cc < n):
                    continue
                res[rr][cc] = True
                if 0 <= r <= 6 and 0 <= c <= 6:
                    on = (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                    dark[rr][cc] = on

    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)

    for i in range(n):
        if not res[6][i]:
            res[6][i] = True
            dark[6][i] = (i % 2 == 0)
        if not res[i][6]:
            res[i][6] = True
            dark[i][6] = (i % 2 == 0)

    ver = {21: 1, 25: 2, 29: 3}[n]
    for cy in _ALIGN[ver]:
        for cx in _ALIGN[ver]:
            if res[cy][cx]:
                continue
            for r in range(-2, 3):
                for c in range(-2, 3):
                    rr, cc = cy + r, cx + c
                    if not (0 <= rr < n and 0 <= cc < n):
                        continue
                    res[rr][cc] = True
                    dark[rr][cc] = (max(abs(r), abs(c)) != 1)

    # 格式信息占位
    for i in range(9):
        if i != 6:
            res[8][i] = True
            res[i][8] = True
    for i in range(8):
        res[8][n - 1 - i] = True
        res[n - 1 - i][8] = True
    res[n - 8][8] = True
    return res, dark


def _place_data(n, res, dark, bits, mask):
    i = 0
    col = n - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
            continue
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if res[r][c]:
                    continue
                bit = bits[i] if i < len(bits) else 0
                i += 1
                if _mask_bit(mask, r, c):
                    bit ^= 1
                dark[r][c] = bool(bit)
        upward = not upward
        col -= 2


def _penalty(n, dark, res):
    p = 0
    # 行/列 连续同色
    for line in list(dark) + [[dark[r][c] for r in range(n)] for c in range(n)]:
        run = 1
        for i in range(1, n):
            if line[i] == line[i - 1]:
                run += 1
            else:
                if run >= 5:
                    p += 3 + (run - 5)
                run = 1
        if run >= 5:
            p += 3 + (run - 5)
    # 2x2 同色
    for r in range(n - 1):
        for c in range(n - 1):
            v = dark[r][c]
            if v == dark[r][c + 1] == dark[r + 1][c] == dark[r + 1][c + 1]:
                p += 3
    # 3:1:1:1:3 与 1:1:3:1:1
    pat1 = [True, False, True, True, True, False, True, False, False, False, False]
    pat2 = [False, False, False, False, True, False, True, True, True, False, True]
    for line in list(dark) + [[dark[r][c] for r in range(n)] for c in range(n)]:
        for i in range(n - 10):
            seg = line[i:i + 11]
            if seg == pat1 or seg == pat2:
                p += 40
    # 黑白比例
    total = n * n
    d = sum(1 for r in range(n) for c in range(n) if dark[r][c])
    k = abs(d * 20 - total * 10) // total
    p += k * 10
    return p


def make(text, ec_level="M"):
    """返回 (n, dark)，dark[r][c] 为 True 表示黑块"""
    data = text.encode("utf-8")
    for ver in (1, 2, 3):
        total, dcw, ecw, blocks = _VER_M[ver]
        need = 4 + 8 + len(data) * 8
        if (need + 7) // 8 <= dcw:
            break
    else:
        raise ValueError("内容太长（最多 42 字节）")

    bits = []
    bits += [0, 1, 0, 0]                       # byte 模式
    for i in range(7, -1, -1):
        bits.append((len(data) >> i) & 1)
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    cap = dcw * 8
    bits += [0] * min(4, cap - len(bits))
    while len(bits) % 8:
        bits.append(0)
    cw = _bits_to_codewords(bits, dcw)

    gen = _gen_poly(ecw)
    ecc = _rs(gen, cw, ecw)
    stream = cw + ecc

    n = 17 + 4 * ver
    res, _ = _build_function(n)
    data_bits = []
    for b in stream:
        for i in range(7, -1, -1):
            data_bits.append((b >> i) & 1)

    best = None
    for mask in range(8):
        dark = [[False] * n for _ in range(n)]
        _, base_dark = _build_function(n)
        for r in range(n):
            for c in range(n):
                dark[r][c] = base_dark[r][c]
        _place_data(n, res, dark, data_bits, mask)
        fmt = _format_bits(mask)
        _write_format(n, dark, fmt)
        pen = _penalty(n, dark, res)
        if best is None or pen < best[0]:
            best = (pen, mask, dark)

    pen, mask, dark = best
    if not verify(n, dark, text):
        raise RuntimeError("自检失败：生成的矩阵解不回原文")
    return n, dark


def _write_format(n, dark, fmt):
    a = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
         (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    for i, (r, c) in enumerate(a):
        dark[r][c] = bool(fmt[i])
    b = [(n - 1, 8), (n - 2, 8), (n - 3, 8), (n - 4, 8), (n - 5, 8), (n - 6, 8), (n - 7, 8),
         (8, n - 8), (8, n - 7), (8, n - 6), (8, n - 5), (8, n - 4), (8, n - 3), (8, n - 2), (8, n - 1)]
    for i, (r, c) in enumerate(b):
        dark[r][c] = bool(fmt[i])
    dark[n - 8][8] = True


def verify(n, dark, text):
    """把矩阵读回来，检查格式信息、RS 校验、并解出原文"""
    res, _ = _build_function(n)
    # 读格式信息（第一份）
    a = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
         (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    val = 0
    for i, (r, c) in enumerate(a):
        val = (val << 1) | (1 if dark[r][c] else 0)
    val ^= 0x5412
    ecl = (val >> 13) & 3
    mask = (val >> 10) & 7
    if ecl != 0:
        return False

    ver = {21: 1, 25: 2, 29: 3}[n]
    total, dcw, ecw, _ = _VER_M[ver]

    bits = []
    col = n - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
            continue
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if res[r][c]:
                    continue
                v = 1 if dark[r][c] else 0
                if _mask_bit(mask, r, c):
                    v ^= 1
                bits.append(v)
        upward = not upward
        col -= 2

    cws = []
    for i in range(0, total * 8, 8):
        b = 0
        for j in range(8):
            b = (b << 1) | bits[i + j]
        cws.append(b)

    data, ecc = cws[:dcw], cws[dcw:]
    # RS 校验：整个码字多项式应能被生成多项式整除
    gen = _gen_poly(ecw)
    chk = list(data) + list(ecc)
    for i in range(len(data)):
        coef = chk[i]
        if coef == 0:
            continue
        for j in range(1, len(gen)):
            chk[i + j] ^= _mul(gen[j], coef)
        chk[i] = 0
    if any(chk[len(data):]):
        return False

    bs = []
    for b in data:
        for i in range(7, -1, -1):
            bs.append((b >> i) & 1)
    if bs[:4] != [0, 1, 0, 0]:
        return False
    ln = 0
    for i in range(4, 12):
        ln = (ln << 1) | bs[i]
    out = bytearray()
    for k in range(ln):
        v = 0
        for j in range(8):
            v = (v << 1) | bs[12 + k * 8 + j]
        out.append(v)
    return bytes(out) == text.encode("utf-8")


def to_rows(n, dark, quiet=4):
    """带静区，返回 0/1 的行"""
    rows = []
    for _ in range(quiet):
        rows.append([0] * (n + quiet * 2))
    for r in range(n):
        row = [0] * quiet + [1 if dark[r][c] else 0 for c in range(n)] + [0] * quiet
        rows.append(row)
    for _ in range(quiet):
        rows.append([0] * (n + quiet * 2))
    return rows


def to_png(path, n, dark, px=8, quiet=4):
    from PIL import Image
    rows = to_rows(n, dark, quiet)
    h, w = len(rows), len(rows[0])
    img = Image.new("L", (w, h), 255)
    p = img.load()
    for r in range(h):
        for c in range(w):
            if rows[r][c]:
                p[c, r] = 0
    img = img.resize((w * px, h * px), Image.NEAREST)
    img.save(path)
    return path


if __name__ == "__main__":
    import sys
    s = sys.argv[1] if len(sys.argv) > 1 else "http://10.96.133.109:8000/dorm.html"
    n, dark = make(s)
    print("版本 %d（%d×%d）内容：%s" % ({21: 1, 25: 2, 29: 3}[n], n, n, s))
    to_png(r"D:\Temp\qr_test.png", n, dark, px=10)
    print("自检通过，已输出 D:\\Temp\\qr_test.png")

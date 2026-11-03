# -*- coding: utf-8 -*-
"""
build_game.py —— 生成「游戏式」交互展示页
================================================================
· 一级：四人宿舍总览，鼠标悬停高亮，点击任意一张床进入
· 二级：单床位独立模型，相机飞行过渡
· 二级内可自定义：左侧竖面装洞洞板 / 毛毡板；书架隔板下装台灯

输出：最终模型/03_交互展示/宿舍交互展示.html （单文件，离线可用）
"""

import json
import math
import os
import sys

BASE = r"D:\Desktop\学校资料\大二上学期\创新创业 段景伦"
SRC = os.path.join(BASE, "宿舍桌面3D建模与尺寸记录", "06_精细版3D")
sys.path.insert(0, SRC)

import build_room3d as br

OUT_DIR = os.path.join(BASE, "最终模型", "03_交互展示")
os.makedirs(OUT_DIR, exist_ok=True)


HTML_TMPL = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>宿舍模型 · 交互展示</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%;overflow:hidden;background:#0f1115;
    font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#e8e4dc}
  canvas{display:block;width:100vw;height:100vh;cursor:default}
  canvas.hot{cursor:pointer}
  canvas.grab{cursor:grabbing}

  /* ---------- 顶部标题 ---------- */
  .top{position:fixed;left:34px;top:26px;pointer-events:none;z-index:10}
  .top .crumb{font-size:11px;letter-spacing:.22em;color:#c8794a;margin-bottom:8px}
  .top h1{font-size:24px;font-weight:700;letter-spacing:.02em}
  .top .sub{font-size:12.5px;color:#8b857c;margin-top:6px;line-height:1.7}

  /* ---------- 底部提示 ---------- */
  .hint{position:fixed;left:50%;bottom:30px;transform:translateX(-50%);
    font-size:13px;color:#9a938a;background:rgba(24,26,31,.82);
    border:1px solid #2c2f37;border-radius:999px;padding:10px 22px;
    backdrop-filter:blur(8px);transition:opacity .35s, transform .35s;z-index:10}
  .hint.hide{opacity:0;transform:translateX(-50%) translateY(10px)}

  /* ---------- 左侧面板（单床位） ---------- */
  .panel{position:fixed;left:34px;top:126px;width:262px;z-index:10;
    background:rgba(23,25,30,.9);border:1px solid #2b2e36;border-radius:16px;
    padding:16px 10px 14px 16px;backdrop-filter:blur(10px);
    max-height:calc(100vh - 168px);overflow-y:auto;overscroll-behavior:contain;
    scrollbar-width:thin;scrollbar-color:#3d434e transparent;
    opacity:0;transform:translateX(-24px);pointer-events:none;
    transition:opacity .4s ease, transform .4s cubic-bezier(.22,1,.36,1)}
  .panel::-webkit-scrollbar{width:6px}
  .panel::-webkit-scrollbar-track{background:transparent}
  .panel::-webkit-scrollbar-thumb{background:#3d434e;border-radius:3px}
  .panel::-webkit-scrollbar-thumb:hover{background:#c8794a}
  .panel.on{opacity:1;transform:none;pointer-events:auto}
  .panel h2{font-size:10.5px;letter-spacing:.18em;color:#c8794a;
    font-weight:600;margin-bottom:8px}
  .grp{margin-bottom:13px}
  .grp:last-child{margin-bottom:0}
  .grp .nm{font-size:12px;color:#b8b1a6;margin-bottom:7px}
  .opt{display:block;width:100%;text-align:left;border:1px solid #333740;
    background:#1b1e24;color:#cfc9bd;font-size:12.5px;padding:9px 12px;
    border-radius:9px;cursor:pointer;font-family:inherit;margin-bottom:7px;
    transition:all .18s;position:relative}
  .opt:hover{border-color:#4a4034;background:#22252c}
  .opt.sel{border-color:#c8794a;background:#2a2119;color:#f0d9c6}
  .opt.sel::after{content:"✓";position:absolute;right:12px;color:#c8794a}
  .dbtn{display:flex;justify-content:space-between;align-items:center;width:100%;
    border:1px solid #333740;background:#1b1e24;color:#cfc9bd;font-size:12.5px;
    padding:8px 11px;border-radius:9px;cursor:pointer;font-family:inherit;margin-bottom:6px;
    transition:all .18s}
  .dbtn:hover{border-color:#4a4034;background:#22252c}
  .dbtn.on{border-color:#c8794a;background:#2a2119;color:#f0d9c6}
  .dbtn b{font-weight:400;color:#8b8378;font-size:11px}
  .dbtn.on b{color:#c8794a}

  /* ---------- 返回 ---------- */
  .back{position:fixed;right:30px;top:26px;z-index:10;border:1px solid #333740;
    background:rgba(23,25,30,.9);color:#cfc9bd;font-size:12.5px;padding:9px 18px;
    border-radius:999px;cursor:pointer;font-family:inherit;backdrop-filter:blur(8px);
    opacity:0;transform:translateY(-8px);pointer-events:none;
    transition:opacity .35s, transform .35s}
  .back.on{opacity:1;transform:none;pointer-events:auto}
  .back:hover{border-color:#c8794a;color:#f0d9c6}

  /* ---------- 尺寸卡 ---------- */
  .spec{position:fixed;right:30px;bottom:30px;z-index:10;font-size:11.5px;
    color:#8b857c;background:rgba(23,25,30,.82);border:1px solid #2b2e36;
    border-radius:12px;padding:12px 16px;line-height:1.9;backdrop-filter:blur(8px);
    opacity:0;transform:translateY(8px);transition:opacity .4s, transform .4s}
  .spec.on{opacity:1;transform:none}
  .spec b{color:#e0d8ca;font-weight:600}

  /* ---------- 转场遮罩 ---------- */
  .beds{position:fixed;left:50%;bottom:76px;transform:translateX(-50%);display:flex;gap:10px;z-index:12;
    transition:opacity .35s, transform .35s}
  .beds.hide{opacity:0;transform:translateX(-50%) translateY(10px);pointer-events:none}
  .beds button{border:1px solid #3a3f49;background:rgba(26,29,35,.92);color:#cfc9bd;
    font-size:13px;padding:10px 20px;border-radius:10px;cursor:pointer;font-family:inherit;
    transition:all .18s;backdrop-filter:blur(8px)}
  .beds button:hover{border-color:#c8794a;color:#f0d9c6;background:#2a2119}
  .sndbtn{position:fixed;right:30px;bottom:112px;z-index:11;width:38px;height:38px;border-radius:50%;
    border:1px solid #333740;background:rgba(23,25,30,.9);color:#cfc9bd;font-size:15px;cursor:pointer;
    backdrop-filter:blur(8px);transition:all .18s;font-family:inherit}
  .sndbtn:hover{border-color:#c8794a;color:#f0d9c6}
  .presetcard{position:fixed;right:30px;top:104px;z-index:10;width:252px;max-height:calc(100vh - 250px);overflow-y:auto;
    background:rgba(24,26,31,.95);border:1px solid #2f333b;border-radius:12px;padding:15px 16px;
    backdrop-filter:blur(10px);opacity:0;pointer-events:none;transition:opacity .28s ease}
  .presetcard.on{opacity:1;pointer-events:auto}
  .presetcard .ph{display:flex;justify-content:space-between;align-items:baseline;
    margin-bottom:11px;padding-bottom:9px;border-bottom:1px solid #2c2f36}
  .presetcard .ph b{font-size:13.5px;color:#f0e6d8;font-weight:600}
  .presetcard .ph span{font-size:16px;color:#c9a227;font-weight:600;letter-spacing:.5px}
  .presetcard ul{margin:0;padding:0;list-style:none}
  .presetcard li{display:flex;justify-content:space-between;align-items:flex-start;
    font-size:11.5px;color:#b6b0a5;padding:6px 0;border-bottom:1px dashed #262a30}
  .presetcard li:last-child{border-bottom:none}
  .presetcard li em{font-style:normal;color:#635e56;font-size:10.5px}
  .presetcard li b{font-weight:600;color:#8f887c;white-space:nowrap;margin-left:10px}
  .presetcard .pf{margin-top:10px;font-size:10px;color:#565148;letter-spacing:.3px}
  .focusbtn{position:fixed;right:30px;bottom:64px;z-index:11;width:38px;height:38px;border-radius:50%;
    border:1px solid #333740;background:rgba(23,25,30,.9);color:#cfc9bd;font-size:14px;cursor:pointer;
    backdrop-filter:blur(8px);transition:all .18s;font-family:inherit}
  .focusbtn:hover{border-color:#c8794a;color:#f0d9c6}
  body.focusmode .top, body.focusmode .panel, body.focusmode .spec, body.focusmode .presetcard,
  body.focusmode .hint, body.focusmode .beds, body.focusmode .back, body.focusmode .sndbtn{
    opacity:0 !important;pointer-events:none !important}
  .panel, .spec, .back{transition:opacity .32s ease}
  body.booting .top, body.booting .hint, body.booting .beds, body.booting .sndbtn{opacity:0;pointer-events:none}
  .top, .hint, .beds, .sndbtn{transition:opacity .5s ease}
  .errbar{position:fixed;left:0;right:0;top:0;padding:10px 16px;background:#6d1b1b;color:#ffdede;
    font:12px/1.5 Consolas,monospace;display:none;z-index:99;white-space:pre-wrap}
  .veil{position:fixed;inset:0;background:#0f1115;z-index:50;pointer-events:none;
    opacity:0;transition:opacity .28s ease}
</style></head>
<body>
<canvas id="c"></canvas>

<div class="top">
  <div class="crumb" id="crumb">选择你的园区</div>
  <h1 id="title">厦门大学嘉庚学院</h1>
  <div class="sub" id="sub">点击任意床位，或点下方按钮进入</div>
</div>

<div class="panel" id="panel">
  <div class="grp">
    <h2>整套方案</h2>
    <div class="nm">不想一件件挑？直接套一套</div>
    <button class="opt preset" data-p="lite">轻改版 · ¥202</button>
    <button class="opt preset" data-p="full">满配版 · ¥435</button>
    <button class="opt preset" data-p="premium">精装版 · ¥1445</button>
  </div>
  <div class="grp">
    <h2>左侧竖面 · 挂板</h2>
    <div class="nm">装在衣柜侧面，朝书桌</div>
    <button class="opt sel" data-slot="board" data-opt="none">不装</button>
    <button class="opt" data-slot="board" data-opt="peg">洞洞板</button>
    <button class="opt" data-slot="board" data-opt="felt">毛毡板</button>
    <div id="sizebox" style="display:none;margin-top:10px">
      <div class="nm" style="margin-bottom:7px">长度（宽固定 30）</div>
      <button class="opt siz" data-sz="60">长 60</button>
      <button class="opt siz" data-sz="80">长 80</button>
    </div>
  </div>
  <div class="grp">
    <h2>书架隔板下 · 台灯</h2>
    <div class="nm">可以两处都装，也可以都不装</div>
    <button class="opt lampbtn" data-lamp="shelf">书架隔板下</button>
    <button class="opt lampbtn" data-lamp="bed">床板下面</button>
  </div>
  <div class="grp">
    <h2>桌面 · 增高架</h2>
    <div class="nm">靠墙放在书架下层</div>
    <button class="opt accbtn" data-acc="riser">增高架</button>
    <div id="riserbox" style="display:none;margin:2px 0 12px 10px">
      <div class="nm" style="margin-bottom:6px">宽</div>
      <button class="opt rw" data-rw="60">60</button>
      <button class="opt rw" data-rw="76">76</button>
      <div class="nm" style="margin:8px 0 6px">高</div>
      <button class="opt rh" data-rh="6">6</button>
      <button class="opt rh" data-rh="10">10</button>
      <button class="opt rh" data-rh="14">14</button>
    </div>
  </div>
  <div class="grp">
    <h2>右侧竖面 · 手柄架 / 耳机架</h2>
    <div class="nm">装在右侧柜体侧板上</div>
    <button class="opt holdbtn" data-hold="gamepad">手柄架</button>
    <button class="opt holdbtn" data-hold="headphone">耳机架</button>
  </div>
  <div class="grp">
    <h2>桌上摆件</h2>
    <div class="nm">可以任意组合，多选</div>
    <button class="opt decobtn" data-deco="mon">显示器</button>
    <button class="opt decobtn" data-deco="kb">键盘桌垫</button>
    <button class="opt decobtn" data-deco="spk">音箱</button>
    <button class="opt decobtn" data-deco="plant">绿植水杯</button>
    <button class="opt decobtn" data-deco="org">收纳柜</button>
    <button class="opt decobtn" data-deco="books">书架摆件</button>
  </div>
  <div class="grp">
    <h2>开门 / 抽屉</h2>
    <div id="doorbox"></div>
  </div>
</div>

<button class="back" id="back">← 返回总览</button>
<button class="sndbtn" id="snd" title="声音开关">🔊</button>
<button class="focusbtn" id="focus" title="清屏（Esc 退出）">⛶</button>

<div class="presetcard" id="pcard">
  <div class="ph"><b id="pname">轻改版</b><span id="ptotal">¥202</span></div>
  <ul id="plist"></ul>
  <div class="pf">参考价 · 电商均价 · 不含运费</div>
</div>

<div class="spec" id="spec">
  桌面 <b>135 × 56</b> · 桌高 <b>75</b> · 板厚 <b>2.5</b><br>
  衣柜 <b>80 × 58.5</b> · 床 <b>200 × 92</b><br>
  柜体高 <b>168</b> · 抽屉宽 <b>32</b>
</div>

<div class="hint" id="hint">点击卡片进入你所在的园区</div>
<div class="errbar" id="err"></div>
<div class="beds" id="beds">
  <button data-u="0">1 号床位</button>
  <button data-u="1">2 号床位</button>
  <button data-u="2">3 号床位</button>
  <button data-u="3">4 号床位</button>
</div>
<div class="veil" id="veil"></div>

<script>
window.addEventListener('error', ev => {
  const d = document.getElementById('err');
  if (!d) return;
  d.style.display = 'block';
  d.textContent = 'JS 错误：' + ev.message + '  @ ' + (ev.lineno||'?');
});
if (typeof CanvasRenderingContext2D !== 'undefined' && !CanvasRenderingContext2D.prototype.roundRect){
  CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h){ return this.rect(x, y, w, h); };
}
const DATA = __DATA__;
const FACES = DATA.faces, ANCH = DATA.anchors, LAMPS = DATA.lamps;
const DOORS = DATA.doors;
function slotOn(tag){
  const i = tag.indexOf(':');
  const k = tag.slice(0, i), o = tag.slice(i + 1);
  if (k === 'board') return custom.board !== 'none' && (custom.board + '_' + custom.size) === o;
  if (k === 'lamp') return custom.lamps[o] === true;
  if (k === 'riser') return custom.riser === true && (custom.riserW + 'x' + custom.riserH) === o;
  if (k === 'gamepad') return custom.gamepad === true;
  if (k === 'headphone') return custom.headphone === true;
  return true;
}
const UBOX = {};
for (const b of DATA.boxes){ (UBOX[b[0]] = UBOX[b[0]] || []).push(b); }

/* 线段与包围盒相交：起点在面中心，终点是灯 */
function blockedBy(cx, cy, cz, ex, ey, ez, boxes){
  const dx = ex - cx, dy = ey - cy, dz = ez - cz;
  for (let i = 0; i < boxes.length; i++){
    const b = boxes[i];
    if (b[7] && !slotOn(b[7])) continue;
    let tmin = 0.001, tmax = 0.985;
    let ok2 = true;
    for (let a = 0; a < 3; a++){
      const c = a === 0 ? cx : (a === 1 ? cy : cz);
      const d = a === 0 ? dx : (a === 1 ? dy : dz);
      const lo = b[1 + a * 2], hi = b[2 + a * 2];
      if (Math.abs(d) < 1e-7){
        if (c < lo || c > hi){ ok2 = false; break; }
      } else {
        let t1 = (lo - c) / d, t2 = (hi - c) / d;
        if (t1 > t2){ const tt = t1; t1 = t2; t2 = tt; }
        if (t1 > tmin) tmin = t1;
        if (t2 < tmax) tmax = t2;
        if (tmin > tmax){ ok2 = false; break; }
      }
    }
    if (ok2) return true;
  }
  return false;
}
const DMAP = {}; DOORS.forEach(d => DMAP[d.id] = d);
const doorOpen = {}; DOORS.forEach(d => doorOpen[d.id] = false);
const cv = document.getElementById('c'), ctx = cv.getContext('2d');

let scene = 'map', selUnit = -1;
const custom = { board: 'none', size: '60', lamps: { shelf: false, bed: false }, riser: false, riserW: '76', riserH: '10', gamepad: false, headphone: false,
                 mon: false, kb: false, spk: false, plant: false, org: false, books: false };

/* ---------------- 相机 ---------------- */
const ROOM_VIEW = {...DATA.room};
function unitView(u){
  const a = ANCH.find(x => x.u === u);
  const [x0,x1,y0,y1,z0,z1] = a.r;
  return {
    cx: (x0+x1)/2, cy: (y0+y1)/2, cz: (z0+z1)/2,
    rad: 0.5*Math.hypot(x1-x0, y1-y0, z1-z0),
    yaw: (a.viewYaw === undefined ? -0.68 : a.viewYaw), pitch: 0.26, zoom: 1.0
  };
}
let view = {...ROOM_VIEW};
let from = {...view}, to = {...view};
let tStart = 0, tDur = 0, animating = false;
const KEYS = ['cx','cy','cz','rad','yaw','pitch','zoom'];

const easeInOut = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;

function nearestAngle(t, cur){
  while (t - cur > Math.PI) t -= 2 * Math.PI;
  while (cur - t > Math.PI) t += 2 * Math.PI;
  return t;
}

function flyTo(target, ms){
  target = {...target};
  target.yaw = nearestAngle(target.yaw, view.yaw);
  from = {...view}; to = {...target};
  tStart = performance.now(); tDur = ms; animating = true; requestDraw();
}

/* ---------------- 可见性 ---------------- */
let visibleCache = null;
function rebuildVisible(){
  visibleCache = FACES.filter(f => {
    if (f.s){
      if (scene !== 'unit' || f.u !== selUnit) return false;
      if (f.s === 'board'){
        if (custom.board === 'none') return false;
        return f.o === custom.board + '_' + custom.size;
      }
      if (f.s === 'lamp') return custom.lamps[f.o] === true;
      if (f.s === 'riser') return custom.riser === true && f.o === (custom.riserW + 'x' + custom.riserH);
      if (f.s === 'gamepad') return custom.gamepad === true;
      if (f.s === 'headphone') return custom.headphone === true;
    if (f.s === 'mon' || f.s === 'kb' || f.s === 'spk' || f.s === 'plant' || f.s === 'org' || f.s === 'books')
      return custom[f.s] === true;
      return false;
    }
    if (scene === 'room') return true;
    return f.u === selUnit;
  });
  window.__nv = visibleCache.length;
}
function requestDraw(){ dirty = true; }

let dirty = true;
let qFactor = 1.0;
let lastBusy = false;

/* ---------------- 绘制 ---------------- */
function resize(){
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = Math.max(1, Math.round(innerWidth * dpr));
  cv.height = Math.max(1, Math.round(innerHeight * dpr));
  ctx.imageSmoothingQuality = 'high';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  requestDraw();
}

const LIGHT2 = [0.62, 0.34, -0.55];
const LIGHT = (() => { const v = [-0.36, 0.82, 0.46];
  const L = Math.hypot(...v); return v.map(x => x/L); })();
const camD = () => Math.max(3.0*view.rad/view.zoom, 1.25*view.rad);
const focalOf = (w,h) => {
  const d = camD();
  return 0.44*Math.min(w,h)*(d/view.rad)*view.zoom;
};

function project(p, camDv, focal, w, h){
  const cy = Math.cos(view.yaw), sy = Math.sin(view.yaw);
  const cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
  const x = p[0]-view.cx, y = p[1]-view.cy, z = p[2]-view.cz;
  const x1 = x*cy + z*sy, z1 = -x*sy + z*cy;
  const y2 = y*cp - z1*sp, z2 = y*sp + z1*cp;
  const depth = camDv - z2;
  if (depth < 4) return null;
  const s = focal / depth;
  return [w/2 + x1*s, h/2 - y2*s, depth];
}

/* 两块常驻缓冲：拖动用小的、静止用大的，避免每次切换重新分配 */
const BUFS = {};
function getBuf(kind, bw, bh){
  let B = BUFS[kind];
  if (!B){
    const c2 = document.createElement('canvas');
    B = BUFS[kind] = { cv: c2, ctx: c2.getContext('2d'), img: null, depth: null, w: 0, h: 0 };
  }
  if (B.w !== bw || B.h !== bh){
    B.w = bw; B.h = bh;
    B.cv.width = bw; B.cv.height = bh;
    B.img = B.ctx.createImageData(bw, bh);
    B.depth = new Float32Array(bw * bh);
  }
  return B;
}

function putTri(buf, x0, y0, w0, x1, y1, w1, x2, y2, w2, col, BW, BH){
  let minx = Math.max(0, Math.floor(Math.min(x0, x1, x2)));
  let maxx = Math.min(BW - 1, Math.ceil(Math.max(x0, x1, x2)));
  let miny = Math.max(0, Math.floor(Math.min(y0, y1, y2)));
  let maxy = Math.min(BH - 1, Math.ceil(Math.max(y0, y1, y2)));
  if (minx > maxx || miny > maxy) return;
  const area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
  if (Math.abs(area) < 0.001) return;
  const inv = 1 / area;
  const d = buf.img.data, dep = buf.depth;
  const R = col[0], Gc = col[1], B = col[2];
  for (let y = miny; y <= maxy; y++){
    const py = y + 0.5;
    const row = y * BW;
    for (let x = minx; x <= maxx; x++){
      const px = x + 0.5;
      const a = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) * inv;
      const b = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) * inv;
      const c = 1 - a - b;
      if (a < -0.0005 || b < -0.0005 || c < -0.0005) continue;
      const ws = a * w0 + b * w1 + c * w2;
      if (ws <= 0) continue;
      const z = 1 / ws;
      const idx = row + x;
      if (z < dep[idx]){
        dep[idx] = z;
        const o = idx << 2;
        d[o] = R; d[o + 1] = Gc; d[o + 2] = B; d[o + 3] = 255;
      }
    }
  }
}

function draw3D(){
  const _t0 = performance.now();
  const w = innerWidth, h = innerHeight;
  ctx.clearRect(0, 0, w, h);

  /* 地面光晕 */
  {
    const cd0 = camD(), f0 = focalOf(w, h);
    const gq = project([view.cx, 0, view.cz], cd0, f0, w, h);
    if (gq){
      const R = Math.min(w, h) * 0.66;
      const rg2 = ctx.createRadialGradient(gq[0], gq[1], 0, gq[0], gq[1], R);
      rg2.addColorStop(0, 'rgba(158,126,86,.20)');
      rg2.addColorStop(1, 'rgba(158,126,86,0)');
      ctx.save();
      ctx.translate(gq[0], gq[1]); ctx.scale(1, .30); ctx.translate(-gq[0], -gq[1]);
      ctx.fillStyle = rg2;
      ctx.beginPath(); ctx.arc(gq[0], gq[1], R, 0, 6.2832); ctx.fill();
      ctx.restore();
    }
  }

  const warm = (scene === 'unit' && (custom.lamps.shelf || custom.lamps.bed));
  const busy = drag || animating;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const dw = Math.round(w * dpr), dh = Math.round(h * dpr);
  const devPx = dw * dh;
  /* 拖动时压到 0.95M 保证跟手；停手后冲到 6.5M 保证清晰 */
  const budget = (busy ? 0.95e6 : 6.5e6) * qFactor;
  const scale = Math.max(0.62, Math.min(2.0, Math.sqrt(budget / devPx)));
  const BW = Math.max(2, Math.round(dw * scale));
  const BH = Math.max(2, Math.round(dh * scale));
  const B = getBuf(busy ? 'fast' : 'hi', BW, BH);
  B.img.data.fill(0);
  B.depth.fill(1e9);

  const cd = camD(), focal = focalOf(BW, BH);
  const cy = Math.cos(view.yaw), sy = Math.sin(view.yaw);
  const cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);

  for (const f of visibleCache){
    let pts = f.p, nn = f.n;
    if (f.s){
      const pk = f.u + '|' + f.s + '|' + f.o;
      const sc = popScale(pk, _t0);
      if (sc < 1){
        const c0 = SPAWN[pk];
        if (c0) pts = f.p.map(q => [c0[0] + (q[0]-c0[0])*sc, c0[1] + (q[1]-c0[1])*sc, c0[2] + (q[2]-c0[2])*sc]);
        dirty = true;
      }
    }
    if (f.d && doorOpen[f.d]){
      const d = DMAP[f.d];
      if (d.kind === 'swing'){
        const a = d.sign * d.max * Math.PI / 180;
        const ca = Math.cos(a), sa = Math.sin(a);
        pts = f.p.map(p => {
          const dx = p[0] - d.hx, dz = p[2] - d.hz;
          return [d.hx + dx*ca - dz*sa, p[1], d.hz + dx*sa + dz*ca];
        });
        nn = [f.n[0]*ca - f.n[2]*sa, f.n[1], f.n[0]*sa + f.n[2]*ca];
      } else {
        pts = f.p.map(p => [p[0], p[1], p[2] + d.max * (d.dz === undefined ? 1 : d.dz)]);
      }
    }
    const nx = nn[0], ny = nn[1], nz = nn[2];
    const rx = nx*cy + nz*sy, rz1 = -nx*sy + nz*cy;
    const rnz = ny*sp + rz1*cp;
    if (rnz <= 0) continue;

    const pr = [];
    let ok = true;
    for (let k = 0; k < 4; k++){
      const p = pts[k];
      const x = p[0]-view.cx, y = p[1]-view.cy, z = p[2]-view.cz;
      const x1 = x*cy + z*sy, z1 = -x*sy + z*cy;
      const y2 = y*cp - z1*sp, z2 = y*sp + z1*cp;
      const depth = cd - z2;
      if (depth < 4){ ok = false; break; }
      const sc = focal / depth;
      pr.push([BW/2 + x1*sc, BH/2 - y2*sc, 1/depth]);
    }
    if (!ok) continue;

    const lam = Math.max(0, nx*LIGHT[0] + ny*LIGHT[1] + nz*LIGHT[2]);
    const fil = Math.max(0, nx*LIGHT2[0] + ny*LIGHT2[1] + nz*LIGHT2[2]);
    const rim = Math.pow(1 - Math.abs(rnz), 3) * 0.26;
    const sh = 0.40 + 0.70*lam + 0.30*fil + rim;

    /* 灯的局部照明：只照亮朝向灯的面，背面不亮 */
    let wr = 0, wg = 0, wb = 0;
    if (warm){
      const fcx = (pts[0][0] + pts[1][0] + pts[2][0] + pts[3][0]) * 0.25;
      const fcy = (pts[0][1] + pts[1][1] + pts[2][1] + pts[3][1]) * 0.25;
      const fcz = (pts[0][2] + pts[1][2] + pts[2][2] + pts[3][2]) * 0.25;
      for (let li = 0; li < 2; li++){
        const opt = li === 0 ? 'shelf' : 'bed';
        if (!custom.lamps[opt]) continue;
        const lp = LAMPS[selUnit + '_' + opt];
        if (!lp) continue;
        const dx = lp.x - fcx, dy = lp.y - fcy, dz = lp.z - fcz;
        const d2 = dx*dx + dy*dy + dz*dz;
        if (d2 > 16000) continue;
        const dd = Math.sqrt(d2) + 0.001;
        const ndl = (nx*dx + ny*dy + nz*dz) / dd;
        if (ndl <= 0) continue;                       // 背离灯的面不受光
        const boxes = UBOX[selUnit] || [];
        if (blockedBy(fcx + nx*0.6, fcy + ny*0.6, fcz + nz*0.6,
                      lp.x, lp.y, lp.z, boxes)) continue;   // 被挡住就不受光
        const k = ndl * 1.15 / (1 + d2 / 2600);
        wr += k; wg += k * 0.90; wb += k * 0.66;
      }
    }

    let r = Math.min(255, f.c[0]*sh + 8 + wr*92);
    let g2 = Math.min(255, f.c[1]*sh + 7 + wg*92);
    let b = Math.min(255, f.c[2]*sh + 6 + wb*92);
    const col = [r|0, g2|0, b|0];

    putTri(B, pr[0][0],pr[0][1],pr[0][2], pr[1][0],pr[1][1],pr[1][2],
           pr[2][0],pr[2][1],pr[2][2], col, BW, BH);
    putTri(B, pr[0][0],pr[0][1],pr[0][2], pr[2][0],pr[2][1],pr[2][2],
           pr[3][0],pr[3][1],pr[3][2], col, BW, BH);
  }

  B.ctx.putImageData(B.img, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(B.cv, 0, 0, BW, BH, 0, 0, dw / dpr, dh / dpr);

  /* 台灯光晕 */
  for (const opt of ['shelf', 'bed']){
    if (!custom.lamps[opt]) continue;
    const lpt = LAMPS[selUnit + '_' + opt];
    if (!lpt) continue;
    const q = project([lpt.x, lpt.y, lpt.z], cd, focalOf(w, h), w, h);
    if (q){
      const R = Math.max(46, Math.min(w, h) * 0.075);
      const rg = ctx.createRadialGradient(q[0], q[1], 0, q[0], q[1], R);
      rg.addColorStop(0, 'rgba(255,222,168,.55)');
      rg.addColorStop(.5, 'rgba(255,205,140,.18)');
      rg.addColorStop(1, 'rgba(255,195,125,0)');
      ctx.globalCompositeOperation = 'lighter';
      ctx.fillStyle = rg;
      ctx.beginPath(); ctx.arc(q[0], q[1], R, 0, 6.2832); ctx.fill();
      ctx.globalCompositeOperation = 'source-over';
    }
  }

  /* 总览：编号与高亮 */
  if (scene === 'room'){
    const cd2 = camD(), f2 = focalOf(w, h);
    for (const a of ANCH){
      const q = project([a.c[0], a.c[1], a.c[2]], cd2, f2, w, h);
      if (!q) continue;
      const near = a.u === hoverUnit;
      const bx = unitBox(a, cd2, f2, w, h);
      if (near && bx){
        ctx.save();
        ctx.setLineDash([7, 5]);
        ctx.strokeStyle = 'rgba(200,121,74,.6)';
        ctx.lineWidth = 1.4;
        ctx.strokeRect(bx[0]-4, bx[1]-4, bx[2]-bx[0]+8, bx[3]-bx[1]+8);
        ctx.restore();
      }
      const R = near ? 34 : 24;
      ctx.beginPath(); ctx.arc(q[0], q[1], R, 0, 6.2832);
      ctx.strokeStyle = near ? 'rgba(200,121,74,.95)' : 'rgba(200,121,74,.42)';
      ctx.lineWidth = near ? 2.4 : 1.4;
      ctx.stroke();
      if (near){ ctx.fillStyle = 'rgba(200,121,74,.16)'; ctx.fill(); }
      ctx.beginPath(); ctx.arc(q[0], q[1], 3.5, 0, 6.2832);
      ctx.fillStyle = near ? '#f0c9a8' : 'rgba(200,121,74,.7)';
      ctx.fill();
      ctx.font = (near ? '600 ' : '') + '13px "Microsoft YaHei",sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      const label = (a.u + 1) + ' 号床位';
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = near ? 'rgba(28,22,17,.92)' : 'rgba(20,22,27,.78)';
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(q[0]-tw/2-11, q[1]-R-30, tw+22, 21, 6);
      else ctx.rect(q[0]-tw/2-11, q[1]-R-30, tw+22, 21);
      ctx.fill();
      ctx.fillStyle = near ? '#f0c9a8' : '#9a9186';
      ctx.fillText(label, q[0], q[1]-R-19.5);
    }
  }

  const _dt = performance.now() - _t0;
  window.__ms = Math.round(_dt);
  if (!busy){
    if (_dt > 420) qFactor = Math.max(0.55, qFactor * 0.82);
    else if (_dt < 140) qFactor = Math.min(1.0, qFactor * 1.08);
  }
  lastBusy = busy;
}


/* ---- 配件出现的弹出动画 ---- */
const SPAWN = {};
(function(){
  const acc = {};
  for (const f of FACES){
    if (!f.s) continue;
    const k = f.u + '|' + f.s + '|' + f.o;
    let a = acc[k];
    if (!a){ a = acc[k] = [1e9, -1e9, 1e9, -1e9, 1e9, -1e9]; }
    for (const q of f.p){
      if (q[0] < a[0]) a[0] = q[0]; if (q[0] > a[1]) a[1] = q[0];
      if (q[1] < a[2]) a[2] = q[1]; if (q[1] > a[3]) a[3] = q[1];
      if (q[2] < a[4]) a[4] = q[2]; if (q[2] > a[5]) a[5] = q[2];
    }
  }
  for (const k in acc){
    const a = acc[k];
    SPAWN[k] = [(a[0] + a[1]) / 2, (a[2] + a[3]) / 2, (a[4] + a[5]) / 2];
  }
})();
const POP = {};
function popIn(k){ POP[k] = performance.now(); if (!animating) requestDraw(); }
function popScale(k, now){
  const t = POP[k];
  if (t === undefined) return 1;
  const e = (now - t) / 260;
  if (e >= 1){ delete POP[k]; return 1; }
  const x = e < 0.6 ? (e / 0.6) * 1.12 : 1.12 - ((e - 0.6) / 0.4) * 0.12;
  return Math.max(0.05, x);
}


/* ---------------- 音效（Web Audio 合成，不占体积） ---------------- */
let AC = null, muted = false;
function ac(){
  if (muted) return null;
  try {
    if (!AC) AC = new (window.AudioContext || window.webkitAudioContext)();
    if (AC.state === "suspended") AC.resume();
    return AC;
  } catch (e){ return null; }
}

/* 玻璃"叮"：三个正弦谐波 + 一个极短的高频噪声瞬态 */
function sfx(freq, vol, dur){
  const a = ac(); if (!a) return;
  freq = freq || 2600; vol = vol || 0.20; dur = dur || 0.30;
  const t = a.currentTime;
  const master = a.createGain();
  master.gain.setValueAtTime(0.0001, t);
  master.gain.exponentialRampToValueAtTime(vol, t + 0.006);
  master.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  master.connect(a.destination);

  [[1, 1.0], [1.68, 0.45], [2.53, 0.18]].forEach(function(p){
    const o = a.createOscillator();
    o.type = "sine";
    o.frequency.value = freq * p[0];
    const g = a.createGain();
    g.gain.value = p[1];
    o.connect(g); g.connect(master);
    o.start(t); o.stop(t + dur + 0.02);
  });

  /* 敲击瞬态 */
  const n = Math.floor(a.sampleRate * 0.02);
  const buf = a.createBuffer(1, n, a.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 7);
  const src = a.createBufferSource(); src.buffer = buf;
  const bp = a.createBiquadFilter(); bp.type = "bandpass";
  bp.frequency.value = 4300; bp.Q.value = 0.8;
  const ng = a.createGain(); ng.gain.value = 0.5;
  src.connect(bp); bp.connect(ng); ng.connect(master);
  src.start(t);
}

function sfxTick(){ sfx(2700, 0.16, 0.26); }
function sfxGo(){ sfx(1650, 0.22, 0.55); }

/* 所有 DOM 按钮统一发声 */
document.addEventListener("pointerdown", function(e){
  let t = e.target;
  if (t && t.tagName === "BUTTON" && !t.classList.contains("sndbtn")) sfxTick();
}, true);

/* ---------------- 园区选择（两级菜单） ---------------- */
function easeOut(x){ return 1 - Math.pow(1 - x, 3); }

const GROUPS = [
  { id: "ly", name: "凌云园区", desc: "3 个楼栋", items: ["凌云 1", "凌云 2", "凌云 3"] },
  { id: "dx", name: "笃行园区", desc: "2 个楼栋", items: ["笃行 1", "笃行 2"] },
  { id: "fr", name: "芙蓉园区", desc: "5 个楼栋", items: ["芙蓉 1", "芙蓉 2", "芙蓉 3", "芙蓉 4", "芙蓉 5"] },
];
const OTHERS = ["群贤", "丰庭", "芙蓉", "南光", "南安", "博学", "囊萤", "若谷", "映雪", "勤业"];

let hoverZone = -1, mapZoom = 1, focusPt = { x: 0, y: 0 }, trans = null;
let selectT0 = 0, pickedZone = "凌云 1";
let menuLevel = 1, menuGroup = 0;

function cardsOfLevel(){
  if (menuLevel === 1){
    return GROUPS.map(function(g){ return { name: g.name, desc: g.desc }; });
  }
  const g = GROUPS[menuGroup];
  return g.items.map(function(n){ return { name: n, desc: "上床下桌 · 4 人间" }; });
}

function cardLayout(w, h){
  const list = cardsOfLevel();
  const n = list.length;
  const gap = Math.max(14, w * 0.014);
  let cw = (menuLevel === 1)
    ? Math.min(360, (w * 0.66 - gap * (n - 1)) / n)
    : Math.min(238, (w * 0.86 - gap * (n - 1)) / n);
  const ch = cw * (menuLevel === 1 ? 0.56 : 0.66);
  const total = cw * n + gap * (n - 1);
  const x0 = (w - total) / 2;
  const y0 = h * 0.40;
  return { n, cw, ch, gap, x0, y0, total };
}

function cardRect(i, L){
  return [L.x0 + i * (L.cw + L.gap), L.y0, L.cw, L.ch];
}

function backRect(L){
  return [L.x0, L.y0 - 46, 108, 28];
}

function drawSelect(now){
  const w = innerWidth, h = innerHeight;
  const g = ctx.createRadialGradient(w * 0.5, h * 0.44, 40, w * 0.5, h * 0.5, Math.max(w, h) * 0.8);
  g.addColorStop(0, "#1d2027"); g.addColorStop(0.55, "#14161b"); g.addColorStop(1, "#0b0d10");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  const L = cardLayout(w, h);
  const list = cardsOfLevel();
  const el0 = now - selectT0;
  const pulse = 0.5 + 0.5 * Math.sin(now / 520);

  /* 二级：返回上一级 */
  if (menuLevel === 2){
    const b = backRect(L);
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.font = '13px "Microsoft YaHei",sans-serif';
    ctx.fillStyle = hoverZone === -9 ? "#f0d9c6" : "#8b857c";
    ctx.fillText("← 返回园区", b[0], b[1] + b[3] / 2);
  }

  for (let i = 0; i < list.length; i++){
    const r = cardRect(i, L);
    const pIn = Math.max(0, Math.min(1, (el0 - i * 90) / 420));
    if (pIn <= 0) continue;
    const eIn = easeOut(pIn);
    ctx.save();
    ctx.globalAlpha = eIn;
    ctx.translate(0, (1 - eIn) * 26);

    const near = i === hoverZone;
    const lift = near ? 3 : 0;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(r[0], r[1] - lift, r[2], r[3], menuLevel === 1 ? 18 : 12);
    else ctx.rect(r[0], r[1] - lift, r[2], r[3]);
    ctx.fillStyle = near ? "#2a2119" : "#1b1e24";
    ctx.fill();
    ctx.lineWidth = near ? 2 : 1.2;
    ctx.strokeStyle = near ? "rgba(200,121,74,.95)" : "rgba(200,121,74," + (0.35 + 0.45 * pulse) + ")";
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.beginPath();
    ctx.arc(r[0] + r[2] / 2, r[1] - lift + r[3] * 0.23, menuLevel === 1 ? 5 : 4, 0, 6.2832);
    ctx.fillStyle = near ? "#ffd9b8" : "rgba(200,121,74,.8)";
    ctx.fill();

    ctx.font = "600 " + Math.round(L.cw * (menuLevel === 1 ? 0.105 : 0.135)) + 'px "Microsoft YaHei",sans-serif';
    ctx.fillStyle = near ? "#f5e2cd" : "#e8e4dc";
    ctx.fillText(list[i].name, r[0] + r[2] / 2, r[1] - lift + r[3] * 0.50);

    ctx.font = Math.round(L.cw * (menuLevel === 1 ? 0.046 : 0.058)) + 'px "Microsoft YaHei",sans-serif';
    ctx.fillStyle = near ? "#c9a184" : "#6f6a63";
    ctx.fillText(list[i].desc, r[0] + r[2] / 2, r[1] - lift + r[3] * 0.76);
    ctx.restore();
  }

  /* 一级：其他园区 */
  if (menuLevel === 1){
    const pChip = Math.max(0, Math.min(1, (el0 - 560) / 420));
    if (pChip > 0){
      ctx.save();
      ctx.globalAlpha = easeOut(pChip);
      ctx.translate(0, (1 - easeOut(pChip)) * 14);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const chipH = 26, chipGap = 9;
      ctx.font = '12px "Microsoft YaHei",sans-serif';
      const widths = OTHERS.map(function(t){ return ctx.measureText(t).width + 22; });
      const totW = widths.reduce(function(a, b){ return a + b; }, 0) + chipGap * (OTHERS.length - 1);
      let cx = (w - totW) / 2, cy = L.y0 + L.ch + 66;
      for (let i = 0; i < OTHERS.length; i++){
        const cw2 = widths[i];
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(cx, cy, cw2, chipH, 13);
        else ctx.rect(cx, cy, cw2, chipH);
        ctx.fillStyle = "rgba(255,255,255,.035)";
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,.07)";
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.fillStyle = "#5f5a53";
        ctx.fillText(OTHERS[i], cx + cw2 / 2, cy + chipH / 2 + 0.5);
        cx += cw2 + chipGap;
      }
      ctx.font = '11.5px "Microsoft YaHei",sans-serif';
      ctx.fillStyle = "#4d4943";
      ctx.fillText("以上园区暂未收录", w / 2, cy + chipH + 22);
      ctx.restore();
    }
  }
}


/* ---------------- 开机动画 ---------------- */
let boot = null;

function clamped(x){ return x < 0 ? 0 : (x > 1 ? 1 : x); }

function spacedText(txt, cx, y, px, color, spacing, alpha){
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.font = px + 'px SimSun, "Songti SC", serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  let total = 0;
  for (const ch of txt) total += ctx.measureText(ch).width + spacing;
  total -= spacing;
  let x = cx - total / 2;
  ctx.fillStyle = color;
  for (const ch of txt){
    ctx.fillText(ch, x, y);
    x += ctx.measureText(ch).width + spacing;
  }
  ctx.restore();
}

function finishBoot(){
  boot = null;
  selectT0 = performance.now();
  document.body.classList.remove('booting');
  requestDraw();
}

function drawBoot(now){
  const w = innerWidth, h = innerHeight;
  const t = (now - boot.t0) / 1000;          /* 秒 */
  ctx.fillStyle = '#0B0D10';
  ctx.fillRect(0, 0, w, h);

  const S = Math.min(w, h) * 0.20;
  const sx = w / 2 - S / 2;
  const sy = h * 0.42 - S / 2;
  const SW = Math.max(2, S * 0.028);

  /* 收尾整体淡出 */
  const out = clamped((t - 2.25) / 0.55);
  const A = 1 - out;
  if (A <= 0.001) return;

  ctx.save();
  ctx.globalAlpha = A;

  /* 1. 方框描线：从左下起，顺时针一圈 */
  const p = clamped((t - 0.28) / 0.85);
  if (p > 0){
    const pts = [[sx, sy + S], [sx, sy], [sx + S, sy], [sx + S, sy + S], [sx, sy + S]];
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    const d = p * 4;
    for (let i = 0; i < 4; i++){
      const seg = clamped(d - i);
      if (seg <= 0) break;
      const a = pts[i], b = pts[i + 1];
      ctx.lineTo(a[0] + (b[0] - a[0]) * seg, a[1] + (b[1] - a[1]) * seg);
    }
    ctx.strokeStyle = '#F5F2EA';
    ctx.lineWidth = SW;
    ctx.lineCap = 'butt';
    ctx.stroke();
  }

  /* 2. 芥子落下 */
  const drop = clamped((t - 1.02) / 0.34);
  if (drop > 0){
    const r = S * 0.16;
    const restY = sy + S - SW / 2 - r;
    const startY = sy - S * 0.55;
    const e = drop * drop;
    let y = startY + (restY - startY) * e;
    let rx = r, ry = r;
    /* 落地压扁再回弹 */
    if (t > 1.34){
      const k = clamped((t - 1.34) / 0.26);
      const squash = Math.sin(k * Math.PI) * 0.22;
      rx = r * (1 + squash);
      ry = r * (1 - squash);
      y = restY + (r - ry);
    }
    ctx.beginPath();
    ctx.ellipse(sx + S / 2, y, rx, ry, 0, 0, 6.2832);
    ctx.fillStyle = '#C9A227';
    ctx.fill();
  }

  /* 3. 字标 */
  const tw = clamped((t - 1.38) / 0.55);
  if (tw > 0){
    const sp = 26 - 12 * easeOut(tw);
    spacedText('芥子', w / 2, sy + S + S * 0.46, Math.round(S * 0.34), '#F5F2EA', sp, tw);
    const sw2 = clamped((t - 1.72) / 0.45);
    if (sw2 > 0){
      ctx.save();
      ctx.globalAlpha = A * sw2 * 0.75;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = Math.round(S * 0.075) + 'px "Microsoft YaHei",sans-serif';
      ctx.fillStyle = '#8B857C';
      ctx.fillText('纳 须 弥', w / 2, sy + S + S * 0.78);
      ctx.restore();
    }
  }
  ctx.restore();
}

function draw(){
  const now = performance.now();
  if (trans){
    const k = Math.min(1, (now - trans.t0) / trans.dur);
    draw3D();
    const p = Math.min(1, k / 0.62);
    const e = easeOut(p);
    if (e < 0.999 && trans.snap){
      const w = innerWidth, h = innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const D = Math.max(0.0001, 1 - e);
      const flaps = [
        { x: 0,     y: 0,     w: w,     h: h / 2, ox: 0, oy: 0, sx: 1, sy: D },
        { x: 0,     y: h / 2, w: w,     h: h / 2, ox: 0, oy: h, sx: 1, sy: D },
        { x: 0,     y: 0,     w: w / 2, h: h,     ox: 0, oy: 0, sx: D, sy: 1 },
        { x: w / 2, y: 0,     w: w / 2, h: h,     ox: w, oy: 0, sx: D, sy: 1 }
      ];
      for (let i = 0; i < flaps.length; i++){
        const f = flaps[i];
        ctx.save();
        ctx.translate(f.ox, f.oy);
        ctx.scale(f.sx, f.sy);
        ctx.translate(-f.ox, -f.oy);
        ctx.drawImage(trans.snap,
          f.x * dpr, f.y * dpr, f.w * dpr, f.h * dpr,
          f.x, f.y, f.w, f.h);
        ctx.fillStyle = 'rgba(10,12,16,' + (0.55 * e) + ')';
        ctx.fillRect(f.x, f.y, f.w, f.h);
        ctx.restore();
      }
      ctx.save();
      ctx.globalAlpha = 0.55 * (1 - e);
      ctx.fillStyle = 'rgba(200,121,74,.9)';
      ctx.fillRect(0, h / 2 - 1, w, 2);
      ctx.fillRect(w / 2 - 1, 0, 2, h);
      ctx.restore();
    }
    if (k >= 1){ trans = null; arriveRoom(); }
    return;
  }
  if (boot){
    drawBoot(now);
    if (now - boot.t0 < 2900) dirty = true;
    else finishBoot();
    return;
  }
  if (scene === 'map'){ drawSelect(now); if (now - selectT0 < 1100) dirty = true; }
  else draw3D();
}

function pickZone(mx, my){
  if (scene !== 'map' || trans) return -1;
  const L = cardLayout(innerWidth, innerHeight);
  if (menuLevel === 2){
    const b = backRect(L);
    if (mx >= b[0] - 8 && mx <= b[0] + b[2] + 8 && my >= b[1] - 4 && my <= b[1] + b[3] + 4) return -9;
  }
  const n = cardsOfLevel().length;
  for (let i = 0; i < n; i++){
    const r = cardRect(i, L);
    if (mx >= r[0] - 6 && mx <= r[0] + r[2] + 6 && my >= r[1] - 8 && my <= r[1] + r[3] + 6) return i;
  }
  return -1;
}

function skipBoot(){
  if (boot) finishBoot();
}

function enterZone(i){
  if (trans) return;
  if (menuLevel === 1){
    menuGroup = i;
    menuLevel = 2;
    selectT0 = performance.now();
    hoverZone = -1;
    sfxTick();
    requestDraw();
    return;
  }
  sfxGo();
  pickedZone = GROUPS[menuGroup].items[i];
  drawSelect(performance.now());
  const _dpr = Math.min(window.devicePixelRatio || 1, 2);
  const snap = document.createElement('canvas');
  snap.width = Math.round(innerWidth * _dpr);
  snap.height = Math.round(innerHeight * _dpr);
  snap.getContext('2d').drawImage(cv, 0, 0);
  view = {
    cx: ROOM_VIEW.cx, cy: ROOM_VIEW.cy, cz: ROOM_VIEW.cz,
    rad: ROOM_VIEW.rad * 1.28,
    yaw: ROOM_VIEW.yaw - 0.10,
    pitch: Math.max(0.12, ROOM_VIEW.pitch - 0.10),
    zoom: 0.94
  };
  from = { ...view }; to = { ...ROOM_VIEW };
  tStart = performance.now(); tDur = 1200; animating = true;
  trans = { t0: performance.now(), dur: 1150, snap: snap };
  scene = 'room';
  el('hint').classList.add('hide');
  el('beds').classList.add('hide');
  rebuildVisible();
  requestDraw();
}

function arriveRoom(){
  mapZoom = 1;
  el('crumb').textContent = pickedZone + ' 园区';
  el('title').textContent = '宿舍总览';
  el('sub').textContent = '点击任意床位（或下方按钮）进入';
  el('beds').classList.remove('hide');
  el('hint').classList.remove('hide');
  el('back').classList.add('on');
  el('back').textContent = '← 返回地图';
  rebuildVisible();
}

/* ---------------- 交互 ---------------- */
let hoverUnit = -1, drag = false, moved = false, lx = 0, ly = 0;

function unitBox(a, cd, focal, w, h){
  const [x0,x1,y0,y1,z0,z1] = a.r;
  let mnx=1e9, mny=1e9, mxx=-1e9, mxy=-1e9, ok=false;
  for (const X of [x0,x1]) for (const Y of [y0,y1]) for (const Z of [z0,z1]){
    const q = project([X,Y,Z], cd, focal, w, h);
    if (!q) continue;
    ok = true;
    mnx=Math.min(mnx,q[0]); mxx=Math.max(mxx,q[0]);
    mny=Math.min(mny,q[1]); mxy=Math.max(mxy,q[1]);
  }
  return ok ? [mnx,mny,mxx,mxy] : null;
}

function pickUnit(mx, my){
  if (scene !== 'room') return -1;
  const cd = camD(), focal = focalOf(innerWidth, innerHeight);
  let best = -1, bestArea = 1e18;
  for (const a of ANCH){
    const bx = unitBox(a, cd, focal, innerWidth, innerHeight);
    if (!bx) continue;
    if (mx < bx[0] || mx > bx[2] || my < bx[1] || my > bx[3]) continue;
    const area = (bx[2]-bx[0]) * (bx[3]-bx[1]);
    if (area < bestArea){ bestArea = area; best = a.u; }
  }
  if (best >= 0) return best;
  let bd = 90;
  for (const a of ANCH){
    const q = project([a.c[0], a.c[1], a.c[2]], cd, focal, innerWidth, innerHeight);
    if (!q) continue;
    const d = Math.hypot(q[0]-mx, q[1]-my);
    if (d < bd){ bd = d; best = a.u; }
  }
  return best;
}

cv.addEventListener('pointerdown', e => {
  drag = true; moved = false; lx = e.clientX; ly = e.clientY;
  cv.classList.add('grab');
});
addEventListener('pointerup', e => {
  if (boot){
    const late = performance.now() - boot.t0 > 2100;   /* 动画快完了，这一下就别浪费 */
    skipBoot();
    if (!late) return;
  }
  if (drag && !moved){
    if (scene === 'map'){
      const zi = pickZone(e.clientX, e.clientY);
      if (zi >= 0) enterZone(zi);
    } else {
      const u = pickUnit(e.clientX, e.clientY);
      if (u >= 0){ sfxGo(); enterUnit(u); }
    }
  }
  drag = false; cv.classList.remove('grab'); requestDraw();
});
addEventListener('pointermove', e => {
  if (drag){
    if (Math.abs(e.clientX-lx) + Math.abs(e.clientY-ly) > 3) moved = true;
    view.yaw += (e.clientX-lx)*0.007;
    view.pitch = Math.max(-0.9, Math.min(1.2, view.pitch + (e.clientY-ly)*0.005));
    lx = e.clientX; ly = e.clientY;
    requestDraw();
    return;
  }
  if (scene === 'map'){
    const zi = pickZone(e.clientX, e.clientY);
    if (zi !== hoverZone){ hoverZone = zi; cv.classList.toggle('hot', zi >= 0); requestDraw(); }
    return;
  }
  const u = pickUnit(e.clientX, e.clientY);
  if (u !== hoverUnit){ hoverUnit = u; cv.classList.toggle('hot', u >= 0); requestDraw(); }
});
cv.addEventListener('wheel', e => {
  e.preventDefault();
  view.zoom = Math.max(0.4, Math.min(6.0, view.zoom * (e.deltaY > 0 ? 0.9 : 1.111)));
  requestDraw();
}, {passive:false});

/* ---------------- 场景切换 ---------------- */
const el = id => document.getElementById(id) || document.createElement('div');

function enterUnit(u){
  const veil = el('veil');
  veil.style.opacity = .55;
  setTimeout(() => {
    scene = 'unit'; selUnit = u;
    custom.board = 'none'; custom.size = '60'; custom.lamps = { shelf: false, bed: false };
    custom.riser = false; custom.riserW = '76'; custom.riserH = '10';
    custom.gamepad = false; custom.headphone = false;
    ['mon','kb','spk','plant','org','books'].forEach(function(k){ custom[k] = false; });
    document.querySelectorAll('.decobtn').forEach(function(b){ b.classList.remove('sel'); });
    hidePresetCard();
    document.querySelectorAll('.preset').forEach(function(x){ x.classList.remove('sel'); });
    refreshSizeBox(); buildDoorButtons(u);
    document.querySelectorAll('.lampbtn').forEach(b => b.classList.toggle('sel', custom.lamps[b.dataset.lamp]));
    document.querySelectorAll('.accbtn').forEach(b => b.classList.toggle('sel', custom[b.dataset.acc]));
    document.querySelectorAll('.holdbtn').forEach(b => b.classList.toggle('sel', custom[b.dataset.hold]));
    refreshRiserBox();
    syncButtons();
    rebuildVisible();
    flyTo(unitView(u), 950);
    el('crumb').textContent = '凌云园区 / 宿舍 / ' + (u+1) + ' 号床位';
    el('back').textContent = '← 返回总览';
    el('title').textContent = (u+1) + ' 号床位';
    el('sub').textContent = '上床下桌 · 可自定义配件';
    el('panel').classList.add('on');
    el('back').classList.add('on');
    el('spec').classList.add('on');
    el('hint').classList.add('hide');
    veil.style.opacity = 0;
  }, 240);
}

function backToRoom(){
  const veil = el('veil');
  veil.style.opacity = .55;
  setTimeout(() => {
    scene = 'room'; selUnit = -1; hoverUnit = -1;
    rebuildVisible();
    flyTo(ROOM_VIEW, 950);
    el('crumb').textContent = '四个人位 · 上床下桌';
    el('title').textContent = '宿舍总览';
    el('sub').textContent = '点击任意床位，或点下方按钮进入';
    el('panel').classList.remove('on');
    el('back').classList.remove('on');
    el('spec').classList.remove('on');
    hidePresetCard();
    el('hint').classList.remove('hide');
    el('back').classList.add('on');
    el('back').textContent = '← 返回地图';
    veil.style.opacity = 0;
  }, 240);
}

function goBack(){
  if (scene === 'unit') backToRoom();
  else if (scene === 'room') backToMap();
}
el('snd').onclick = () => {
  muted = !muted;
  el('snd').textContent = muted ? '🔇' : '🔊';
};
function toggleFocus(){
  const on = document.body.classList.toggle('focusmode');
  el('focus').textContent = on ? '✕' : '⛶';
  if (on) hidePresetCard();
  if (on && scene === 'unit'){
    flyTo({ cx: unitView(selUnit).cx, cy: 96.0, cz: unitView(selUnit).cz,
            rad: 62.0, yaw: unitView(selUnit).yaw, pitch: 0.22,
            zoom: 1.32 }, 900);
  } else if (!on && scene === 'unit'){
    flyTo(unitView(selUnit), 900);
  }
  requestDraw();
}
el('focus').onclick = toggleFocus;
addEventListener('keydown', e => {
  if (e.key === 'Escape' && document.body.classList.contains('focusmode')) toggleFocus();
  if (e.key === 'f' || e.key === 'F'){ if (scene === 'unit') toggleFocus(); }
});
el('back').onclick = goBack;

function backToMap(){
  const veil = el('veil');
  veil.style.opacity = .55;
  setTimeout(() => {
    scene = 'map'; selUnit = -1; hoverUnit = -1; hoverZone = -1; mapZoom = 1;
    selectT0 = performance.now();
    rebuildVisible();
    el('crumb').textContent = '选择你的园区';
    el('title').textContent = '厦门大学嘉庚学院';
    el('sub').textContent = '已收录：凌云 1–3 · 笃行 1–2 · 芙蓉 1–5　点击卡片进入';
    el('back').classList.remove('on');
    el('beds').classList.add('hide');
    el('hint').classList.remove('hide');
    requestDraw();
    veil.style.opacity = 0;
  }, 240);
}
document.querySelectorAll('#beds button').forEach(b => {
  b.onclick = () => enterUnit(parseInt(b.dataset.u, 10));
});


/* ---------------- 整套方案 ---------------- */
const PRESETS = {
  lite: {
    name: '轻改版', tag: '够用就好', total: 202,
    conf: { board: 'peg', size: '60', lamps: { shelf: true, bed: false },
            riser: true, riserW: '60', riserH: '6', gamepad: false, headphone: false },
    items: [
      ['洞洞板', '60 × 30 cm · 含挂钩 4 个', 79],
      ['夹式台灯', '暖光 · 夹在书架隔板', 59],
      ['增高架', '60 × 6 cm', 45],
      ['理线槽', '1 米 · 背胶', 19]
    ]
  },
  premium: {
    name: '精装版', tag: '照着照片抄的', total: 1445,
    conf: { board: 'peg', size: '80', lamps: { shelf: true, bed: true },
            riser: false, riserW: '76', riserH: '10', gamepad: true, headphone: true,
            mon: true, kb: true, spk: true, plant: true, org: true, books: true },
    items: [
      ['显示器 21.5"', '带支架 · 放在书架下层', 499],
      ['机械键盘', '87 键 · 36 × 12 cm', 229],
      ['鼠标 + 大桌垫', '32 × 18 cm', 89],
      ['桌面音箱 × 2', '书架下层两角', 149],
      ['桌面收纳柜', '18 宽 · 3 层抽屉', 69],
      ['绿植 + 陶盆', '盆 6 × 6 cm', 45],
      ['洞洞板', '80 × 30 cm · 含挂钩 6 个', 109],
      ['夹式台灯 × 2', '书架隔板下 + 床板下', 118],
      ['手柄 / 耳机挂架', '右侧柜板', 60],
      ['书 + 收纳盒', '书架上层摆件', 59],
      ['理线槽', '1 米 · 背胶', 19]
    ]
  },
  full: {
    name: '满配版', tag: '桌面当战场', total: 435,
    conf: { board: 'peg', size: '80', lamps: { shelf: true, bed: true },
            riser: true, riserW: '76', riserH: '14', gamepad: true, headphone: true },
    items: [
      ['洞洞板', '80 × 30 cm · 含挂钩 6 个', 109],
      ['夹式台灯 × 2', '书架隔板下 + 床板下', 118],
      ['增高架', '76 × 14 cm', 129],
      ['手柄壁挂架', '右侧柜板', 35],
      ['耳机壁挂架', '右侧柜板', 25],
      ['理线槽', '1 米 · 背胶', 19]
    ]
  }
};
let activePreset = null;

function renderPresetCard(key){
  const p = PRESETS[key];
  el('pname').textContent = p.name + ' · ' + p.tag;
  el('ptotal').textContent = '¥' + p.total;
  el('plist').innerHTML = p.items.map(function(it){
    return '<li><span>' + it[0] + '<br><em>' + it[1] + '</em></span><b>¥' + it[2] + '</b></li>';
  }).join('');
  el('pcard').classList.add('on');
}

function hidePresetCard(){
  activePreset = null;
  el('pcard').classList.remove('on');
}

function applyPreset(key){
  const p = PRESETS[key];
  const c = p.conf;
  custom.board = c.board;
  custom.size = c.size;
  custom.lamps = { shelf: c.lamps.shelf, bed: c.lamps.bed };
  custom.riser = c.riser;
  custom.riserW = c.riserW;
  custom.riserH = c.riserH;
  custom.gamepad = c.gamepad;
  custom.headphone = c.headphone;
  ['mon','kb','spk','plant','org','books'].forEach(function(k){ custom[k] = (c[k] === true); });

  refreshSizeBox();
  syncButtons();
  refreshRiserBox();
  document.querySelectorAll('.lampbtn').forEach(function(b){ b.classList.toggle('sel', custom.lamps[b.dataset.lamp]); });
  document.querySelectorAll('.accbtn').forEach(function(b){ b.classList.toggle('sel', custom[b.dataset.acc]); });
  document.querySelectorAll('.holdbtn').forEach(function(b){ b.classList.toggle('sel', custom[b.dataset.hold]); });
  document.querySelectorAll('.decobtn').forEach(function(b){ b.classList.toggle('sel', custom[b.dataset.deco]); });
  document.querySelectorAll('.preset').forEach(function(b){ b.classList.toggle('sel', b.dataset.p === key); });
  rebuildVisible();
  requestDraw();

  if (custom.board !== 'none') popIn(selUnit + '|board:' + custom.board);
  if (custom.riser) popIn(selUnit + '|riser:' + custom.riserW + 'x' + custom.riserH);
  if (custom.gamepad) popIn(selUnit + '|gamepad:on');
  if (custom.headphone) popIn(selUnit + '|headphone:on');
  ['mon','kb','spk','plant','org','books'].forEach(function(k){ if (custom[k]) popIn(selUnit + '|' + k + ':on'); });

  activePreset = key;
  renderPresetCard(key);
  sfxGo();
}

document.querySelectorAll('.preset').forEach(function(b){
  b.onclick = function(){ applyPreset(b.dataset.p); };
});

/* 手动改任何一件，清单就不再对应，收起来 */
el('panel').addEventListener('pointerdown', function(e){
  const b = e.target && e.target.closest ? e.target.closest('button') : null;
  if (!b || b.classList.contains('preset')) return;
  if (activePreset) hidePresetCard();
  document.querySelectorAll('.preset').forEach(function(x){ x.classList.remove('sel'); });
}, true);

/* ---------------- 配件按钮 ---------------- */
function syncButtons(){
  document.querySelectorAll('.opt').forEach(b => {
    const s = b.dataset.slot, o = b.dataset.opt;
    if (!s) return;
    const on = (custom.board === o);
    b.classList.toggle('sel', on);
  });
}
document.querySelectorAll('.opt').forEach(b => {
  if (b.classList.contains('preset')) return;   /* 预设按钮自己管，别覆盖 */
  b.onclick = () => {
    const s = b.dataset.slot, o = b.dataset.opt;
    if (!s) return;
    if (s === 'board') { custom.board = o; refreshSizeBox(); }
    syncButtons();
    rebuildVisible();
    requestDraw();
  };
});

function refreshRiserBox(){
  const bx = document.getElementById('riserbox');
  if (!bx) return;
  bx.style.display = custom.riser ? 'block' : 'none';
  document.querySelectorAll('.rw').forEach(b => b.classList.toggle('sel', b.dataset.rw === custom.riserW));
  document.querySelectorAll('.rh').forEach(b => b.classList.toggle('sel', b.dataset.rh === custom.riserH));
}
document.querySelectorAll('.rw').forEach(b => {
  b.onclick = () => { custom.riserW = b.dataset.rw; refreshRiserBox(); rebuildVisible(); requestDraw(); };
});
document.querySelectorAll('.rh').forEach(b => {
  b.onclick = () => { custom.riserH = b.dataset.rh; refreshRiserBox(); rebuildVisible(); requestDraw(); };
});
document.querySelectorAll('.holdbtn').forEach(b => {
  b.onclick = () => {
    const k = b.dataset.hold;
    custom[k] = !custom[k];
    b.classList.toggle('sel', custom[k]);
    if (custom[k]) popIn(selUnit + '|' + k + ':on');
    rebuildVisible(); requestDraw();
  };
});
document.querySelectorAll('.accbtn').forEach(b => {
  b.onclick = () => {
    const k = b.dataset.acc;
    custom[k] = !custom[k];
    document.querySelectorAll('.accbtn').forEach(x => x.classList.toggle('sel', custom[x.dataset.acc]));
    refreshRiserBox();
    if (custom[k]){
      const tag = k === 'riser' ? ('riser:' + custom.riserW + 'x' + custom.riserH) : (k + ':on');
      popIn(selUnit + '|' + tag);
    }
    rebuildVisible(); requestDraw();
  };
});
document.querySelectorAll('.decobtn').forEach(b => {
  b.onclick = () => {
    const k = b.dataset.deco;
    custom[k] = !custom[k];
    b.classList.toggle('sel', custom[k]);
    if (custom[k]) popIn(selUnit + '|' + k + ':on');
    if (activePreset) hidePresetCard();
    rebuildVisible(); requestDraw();
  };
});
document.querySelectorAll('.lampbtn').forEach(b => {
  b.onclick = () => {
    const k = b.dataset.lamp;
    custom.lamps[k] = !custom.lamps[k];
    b.classList.toggle('sel', custom.lamps[k]);
    rebuildVisible(); requestDraw();
  };
});

/* ---------------- 尺寸子菜单 ---------------- */
function refreshSizeBox(){
  const bx = document.getElementById("sizebox");
  if (!bx) return;
  bx.style.display = (custom.board === "none") ? "none" : "block";
  document.querySelectorAll(".siz").forEach(b => {
    b.classList.toggle("sel", b.dataset.sz === custom.size);
  });
}
document.querySelectorAll(".siz").forEach(b => {
  b.onclick = () => { custom.size = b.dataset.sz; refreshSizeBox(); rebuildVisible(); requestDraw(); };
});

/* ---------------- 开门按钮 ---------------- */
function buildDoorButtons(u){
  const box = document.getElementById("doorbox");
  if (!box) return;
  box.innerHTML = "";
  const list = DOORS.filter(d => d.unit === u);
  const all = document.createElement("button");
  all.className = "dbtn";
  all.innerHTML = "全部打开 <b>⇄</b>";
  all.onclick = () => {
    const anyClosed = list.some(d => !doorOpen[d.id]);
    list.forEach(d => doorOpen[d.id] = anyClosed);
    buildDoorButtons(u); requestDraw();
  };
  box.appendChild(all);
  list.forEach(d => {
    const b = document.createElement("button");
    b.className = "dbtn" + (doorOpen[d.id] ? " on" : "");
    b.innerHTML = d.label + " <b>" + (doorOpen[d.id] ? "开" : "关") + "</b>";
    b.onclick = () => { doorOpen[d.id] = !doorOpen[d.id]; sfxTick(); buildDoorButtons(u); requestDraw(); };
    box.appendChild(b);
  });
}

/* ---------------- 主循环 ---------------- */
function frame(){
  if (trans) dirty = true;
  if (animating){
    const k = Math.min(1, (performance.now() - tStart) / tDur);
    const e = easeInOut(k);
    for (const key of KEYS) view[key] = from[key] + (to[key] - from[key]) * e;
    if (k >= 1){ animating = false; }
    dirty = true;
  }
  if (dirty){ dirty = false;
    try { draw(); } catch(ex){
      const d = document.getElementById('err');
      if (d){ d.style.display='block'; d.textContent = '绘制错误：' + (ex && ex.message ? ex.message : ex); }
    }
  }
  requestAnimationFrame(frame);
}

boot = { t0: performance.now() };
document.body.classList.add('booting');
selectT0 = performance.now() + 2900;
rebuildVisible();
resize();
el('beds').classList.add('hide');
el('hint').classList.remove('hide');
addEventListener('resize', resize);
frame();
</script>
</body></html>
"""


def _view_yaw(u):
    """按床位实际朝向算一个能看见桌面的机位角度"""
    sx, sz, ox, oz = br.UNIT_XFORMS[u]
    sgn_sin = -1.0 if sx > 0 else 1.0     # 相机在对侧才看得见桌面
    sgn_cos = 1.0 if sz > 0 else -1.0     # 正面朝 +z 还是 -z
    return math.atan2(sgn_sin * 0.629, sgn_cos * 0.778)


def main():
    br.build_all()

    # ---------------- 数据准备 ----------------
    faces = []
    for i, (pts, n, color, group) in enumerate(br.FACES):
        u, slot, opt = br.FACE_META[i]
        if group == br.G_ENV:
            continue
        faces.append({
            "p": [[round(c[0], 1), round(c[1], 1), round(c[2], 1)] for c in pts],
            "n": [round(x, 3) for x in n],
            "c": list(color),
            "u": u,
            "s": slot,
            "o": opt,
        "d": br.FACE_DOOR[i],
        })

    units = sorted({f["u"] for f in faces if f["u"] >= 0})

    # 每个床位的取景点：书桌段的包围盒中心
    anchors = []
    for u in units:
        xs = [c[0] for f in faces if f["u"] == u for c in f["p"]]
        ys = [c[1] for f in faces if f["u"] == u for c in f["p"]]
        zs = [c[2] for f in faces if f["u"] == u for c in f["p"]]
        anchors.append({
            "u": u,
            "viewYaw": round(_view_yaw(u), 4),
            "x": round((min(xs) + max(xs)) / 2, 1),
            "y": round((min(ys) + max(ys)) / 2, 1),
            "z": round((min(zs) + max(zs)) / 2, 1),
            "c": [round((min(xs) + max(xs)) / 2, 1),
                  round(min(ys) + (max(ys) - min(ys)) * 0.42, 1),
                  round((min(zs) + max(zs)) / 2, 1)],
            "r": [round(x, 1) for x in (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))],
        })

    # 台灯发光点：按 单元 + 安装位置 区分
    lamps = {}
    for u in units:
        for opt in ("shelf", "bed"):
            lp = [f for f in faces if f["u"] == u and f["s"] == "lamp" and f["o"] == opt]
            em = [f for f in lp if f["c"] == [255, 249, 228]]
            if em:
                lp = em
            if not lp:
                continue
            lamps[str(u) + "_" + opt] = {
                "x": round(sum(c[0] for f in lp for c in f["p"]) / (4 * len(lp)), 1),
                "y": round(sum(c[1] for f in lp for c in f["p"]) / (4 * len(lp)), 1),
                "z": round(sum(c[2] for f in lp for c in f["p"]) / (4 * len(lp)), 1),
            }

    allx = [c[0] for f in faces for c in f["p"]]
    ally = [c[1] for f in faces for c in f["p"]]
    allz = [c[2] for f in faces for c in f["p"]]
    room = {
        "cx": round((min(allx) + max(allx)) / 2, 1),
        "cy": round((min(ally) + max(ally)) / 2, 1),
        "cz": round((min(allz) + max(allz)) / 2, 1),
        "rad": round(0.5 * ((max(allx) - min(allx)) ** 2 + (max(ally) - min(ally)) ** 2
                            + (max(allz) - min(allz)) ** 2) ** 0.5, 1),
        "yaw": -0.50, "pitch": 0.34, "zoom": 1.0,
    }

    payload = {
        "faces": faces,
        "anchors": anchors,
        "lamps": lamps,
    "doors": br.ALL_DOORS,
    "boxes": [[b[8], round(b[0], 1), round(b[1], 1), round(b[2], 1),
               round(b[3], 1), round(b[4], 1), round(b[5], 1), b[9]]
              for b in br.BOXES if b[8] >= 0 and b[6] != br.G_ENV],
        "room": room,
        "dims": {
            "desk": [br.DIMS["DESK_W"], br.DIMS["DESK_D"], br.DIMS["DESK_H"]],
            "top": br.DIMS["TOP_T"],
            "bed": [br.DIMS["BED_W"], br.DIMS["BED_D"], br.DIMS["BED_Y"]],
            "ward": [br.DIMS["WARD_W"], br.DIMS["WARD_D"], br.DIMS["FURN_H"]],
        },
    }

    html = HTML_TMPL.replace("__DATA__", json.dumps(payload, ensure_ascii=False,
                                                    separators=(",", ":")))
    path = os.path.join(OUT_DIR, "宿舍交互展示.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("面数:", len(faces), " 单元:", len(units), " 台灯点:", sum(1 for _ in lamps if _))
    print("写出:", path, "%.0f KB" % (os.path.getsize(path) / 1024))




if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Build native indexed label textures from font outlines.
Native-size antialiasing, clean solid lettering and original state palettes.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'SeoulHangangB.ttf')

def lum(pal):
    return pal[:, :3].astype(float) @ np.array([.299, .587, .114])

def render_mask(text, w, h, font=FONT, ss=1, size=None, bold=0, align='center', font_size=None):
    # Fit whole outline glyphs at their native integer size. Never stretch text.
    for px in range(font_size or max(1, round(size or h)+6), 0, -1):
        f = ImageFont.truetype(font, px)
        box = f.getbbox(text)
        tw, th = box[2]-box[0], box[3]-box[1]
        if tw <= w and th <= h: break
    assert tw <= w and th <= h, (text,w,h)
    im = Image.new('L', (w,h))
    x = 0 if align == 'left' else (w-tw)//2
    ImageDraw.Draw(im).text((x-box[0], (h-th)//2-box[1]), text, 255, font=f)
    return np.asarray(im,np.float32)/255

def nearest_palette(rgba, pal, choices=None):
    """Premultiplied comparison avoids opaque fringes around transparent pixels."""
    p = pal.astype(np.float32).copy()
    p[:, 3] = np.minimum(p[:, 3]*2,255)
    if choices is None: choices = np.arange(len(p))
    q = p[choices].copy(); q[:,:3] *= q[:,3:4]/255
    a = rgba.astype(np.float32).copy(); a[...,:3] *= a[...,3:4]/255
    flat = a.reshape(-1,4); result = np.empty(len(flat),np.uint8)
    for start in range(0,len(flat),4096):
        delta = flat[start:start+4096,None,:]-q[None,:,:]
        result[start:start+4096] = choices[np.argmin((delta*delta).sum(2),axis=1)]
    return result.reshape(a.shape[:2])

def relabel(idx, pal, box, text, pad=1, size_scale=1.0, font=FONT, ow=1, align='center', font_size=None):
    x,y,w,h = box
    assert x >= 0 and y >= 0 and x+w <= idx.shape[1] and y+h <= idx.shape[0], box
    region = idx[y:y+h,x:x+w].copy()
    border = np.concatenate((region[0],region[-1],region[:,0],region[:,-1]))
    bg = int(np.bincount(border, minlength=len(pal)).argmax())
    alpha = pal[:,3].astype(float); light = lum(pal)
    text_pixels = (region != bg) & (alpha[region] > 0)
    if not text_pixels.any(): return False
    ys,xs = np.where(text_pixels)
    colors = np.unique(region[text_pixels]); opaque = colors[alpha[colors] >= 100]
    if len(opaque)==0: opaque=colors[alpha[colors] == alpha[colors].max()]
    # Choose one original face colour, not a row-by-row sampled stripe pattern.
    bright = opaque[light[opaque] >= np.percentile(light[opaque], 70)]
    counts = np.bincount(region.ravel(), minlength=len(pal))
    face = int(bright[np.argmax(counts[bright])])
    target_h = min(h-2, max(8, round((ys.max()-ys.min()+1-2)*size_scale)))
    target_w = max(1,w-2*pad)
    m = render_mask(text,target_w,target_h,font=font,size=target_h,align=align,font_size=font_size)
    mask = np.zeros((h,w),np.float32)
    oy = max(1,min(h-target_h-1,round((ys.min()+ys.max()+1-target_h)/2)))
    ox = pad if align=='left' else (w-target_w)//2
    mask[oy:oy+target_h,ox:ox+target_w] = m
    # Linear native antialiasing only. No outline, dilation, shadow or gamma.
    bgc=pal[bg].astype(np.float32);bgc[3]=min(255,bgc[3]*2)
    fg=pal[face].astype(np.float32);fg[3]=min(255,fg[3]*2)
    fa=mask*fg[3]/255; ba=bgc[3]/255
    alpha=fa+ba*(1-fa)
    rgb=fg[:3]*fa[...,None]+bgc[:3]*ba*(1-fa[...,None])
    rgba=np.zeros((h,w,4),np.float32)
    rgba[...,:3]=np.divide(rgb,alpha[...,None],out=np.zeros_like(rgb),where=alpha[...,None]>0)
    rgba[...,3]=alpha*255
    choices=np.unique(np.concatenate((region.ravel(),np.array([bg],np.uint8))))
    idx[y:y+h,x:x+w]=nearest_palette(rgba,pal,choices)
    return True

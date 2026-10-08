#!/usr/bin/env python3
"""
Render the weekly PTY Live Mix: a 9:16 reel (MP4) and a 4:5 carousel (PNG).

    python3 ptymix.py week.json outdir                      # silent reel + carousel
    python3 ptymix.py week.json outdir bed.mp3 --music-start 24

week.json is written by mix_week.py (or by hand): a cover, one "feature" slide
per headline show with genre artwork, one slide per day listing everything
else, and a closing slide. Timing is derived from how much there is to read.

With a music file the silent render is removed afterwards, so the folder holds
exactly one MP4 -- publish_buffer.py posts the first MP4 it finds, and two
would make which one goes out a matter of filename sort.

Every slide is measured before it is drawn. A slide whose text would run into
the brand line stops the build: nobody looks at these before they are posted,
so an overflow has to be an error rather than something a reviewer catches.
"""
import argparse, glob, json, math, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W=1080; FPS=30; X=84; MW=W-2*X
def fp(n): return glob.glob("/usr/share/fonts/**/"+n, recursive=True)[0]
HB=fp("DejaVuSansCondensed-Bold.ttf"); RB=fp("LiberationSans-Bold.ttf"); RR=fp("LiberationSans-Regular.ttf")
def F(p,s): return ImageFont.truetype(p,s)
def hx(h,a=255):
    h=h.lstrip('#'); return (int(h[0:2],16),int(h[2:4],16),int(h[4:6],16),a)
BASE=hx('#0b0a12'); WHITE=(255,255,255,255)
MD=ImageDraw.Draw(Image.new('RGBA',(10,10)))
def wrap(text,font,size,maxlines):
    while True:
        f=F(font,size); lines=[]; cur=""
        for w in text.split():
            t=(cur+" "+w).strip()
            if MD.textlength(t,font=f)<=MW: cur=t
            else:
                if cur: lines.append(cur)
                cur=w
        lines.append(cur)
        if len(lines)<=maxlines and all(MD.textlength(l,font=f)<=MW for l in lines): return f,lines
        size-=4
# ---------- genre artwork (drawn at 2x, covers top area) ----------
def art(kind,acc,H,cy):
    S=2; ov=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); d=ImageDraw.Draw(ov); a=hx(acc); rnd=random.Random(7)
    top=int((cy+330)*S)
    if kind=='vinyl':
        cx=780*S; c=cy*S
        for i,rr in enumerate(range(140,900,38)):
            r=rr*S; d.ellipse((cx-r,c-r,cx+r,c+r),outline=(255,255,255,70 if i%4==0 else 28),width=3 if i%4==0 else 2)
        r=110*S; d.ellipse((cx-r,c-r,cx+r,c+r),fill=a[:3]+(235,)); r=18*S; d.ellipse((cx-r,c-r,cx+r,c+r),fill=BASE)
    elif kind=='punk':
        x=-600*S
        while x<W*S+200:
            w=rnd.choice([26,54,90,140])*S; al=rnd.choice([40,70,120,200])
            col=a[:3]+(al,) if rnd.random()<0.7 else (255,255,255,int(al*0.5))
            d.polygon([(x,top),(x+w,top),(x+w+520*S,0),(x+520*S,0)],fill=col); x+=w+rnd.choice([30,60,110])*S
        for gy in range(0,top,34*S):
            for gx in range(0,W*S,34*S):
                r=int((1-gy/top)*9*S)
                if r>1: d.ellipse((gx-r,gy-r,gx+r,gy+r),fill=(11,10,18,120))
    elif kind=='electro':
        hz=int(cy*S*0.55)
        for i in range(0,26):
            t=(i/25)**2.2; y=hz+int(t*(top-hz)); d.line((0,y,W*S,y),fill=a[:3]+(40+int(150*t),),width=3)
        for i in range(-14,15):
            d.line((W*S//2+i*40*S,hz,W*S//2+i*260*S,top),fill=a[:3]+(110,),width=3)
        for k,(amp,fr,al) in enumerate([(70,2.2,230),(46,3.7,150),(30,5.9,100)]):
            pts=[(x,int(hz*0.52+amp*S*math.sin(x/(W*S)*math.pi*2*fr+k)*math.sin(x/(W*S)*math.pi))) for x in range(0,W*S+1,8)]
            d.line(pts,fill=(255,255,255,al) if k==0 else a[:3]+(al,),width=7 if k==0 else 5)
    elif kind=='metal':
        for i in range(13):
            x0=i*W*S/12; h=rnd.uniform(0.35,1.0)*top*0.55
            d.polygon([(x0-70*S,0),(x0+70*S,0),(x0,h)],fill=a[:3]+(rnd.choice([70,110,170]),))
        for b in range(3):
            x=rnd.uniform(0.2,0.85)*W*S; y=0; pts=[(x,y)]
            while y<top*0.95:
                y+=rnd.uniform(50,120)*S; x+=rnd.uniform(-110,110)*S; pts.append((x,y))
            d.line(pts,fill=a[:3]+(120,),width=22); d.line(pts,fill=(255,255,255,240),width=7)
    elif kind=='candle':
        bok=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); bd=ImageDraw.Draw(bok)
        for i in range(46):
            x=rnd.uniform(0,W*S); y=rnd.uniform(0,top); r=rnd.uniform(18,74)*S
            bd.ellipse((x-r,y-r,x+r,y+r),fill=a[:3]+(rnd.randint(40,130),))
        ov.alpha_composite(bok.filter(ImageFilter.GaussianBlur(14)))
        for i in range(7):
            x=int((120+i*140)*S); by=int(top-rnd.uniform(40,170)*S); fh=rnd.uniform(70,105)*S; fw=fh*0.36
            d.rectangle((x-13*S,by+8*S,x+13*S,top+60*S),fill=(255,244,220,200))
            d.polygon([(x,by-fh),(x+fw,by-fh*0.25),(x,by+8*S),(x-fw,by-fh*0.25)],fill=a[:3]+(255,))
            d.ellipse((x-fw,by-fh*0.55,x+fw,by+8*S),fill=a[:3]+(255,))
            d.ellipse((x-fw*0.45,by-fh*0.32,x+fw*0.45,by+2*S),fill=(255,250,225,255))
    return ov
def bg(kind,acc,H,ty):
    S=2; a=hx(acc); im=Image.new('RGBA',(W*S,H*S),BASE); cy=max(260,ty-330)
    g=Image.new('RGBA',(1,H*S))
    for y in range(H*S):
        t=max(0,1-y/(H*S*0.8)); g.putpixel((0,y),a[:3]+(int(110*t*t),))
    im.alpha_composite(g.resize((W*S,H*S)))
    gl=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); r=560*S
    ImageDraw.Draw(gl).ellipse((760*S-r,cy*S-r,760*S+r,cy*S+r),fill=a[:3]+(110,))
    im.alpha_composite(gl.filter(ImageFilter.GaussianBlur(220)))
    im.alpha_composite(art(kind,acc,H,cy))
    sh=Image.new('RGBA',(1,H*S)); y0=(ty-260)*S; y1=(ty+40)*S
    for y in range(H*S):
        t=min(1,max(0,(y-y0)/(y1-y0))); sh.putpixel((0,y),BASE[:3]+(int(238*t*t*(3-2*t)),))
    im.alpha_composite(sh.resize((W*S,H*S)))
    return im.resize((W,H),Image.LANCZOS)
# ---------- text blocks: draw on a layer, measure, bottom-anchor ----------
class Blk:
    def __init__(s): s.im=Image.new('RGBA',(W,1700),(0,0,0,0)); s.d=ImageDraw.Draw(s.im); s.y=0
    def pill(s,text,acc):
        f=F(RB,38); t=text.upper(); tw=sum(s.d.textlength(c,font=f)+5 for c in t)
        s.d.rounded_rectangle((X,s.y,X+tw+56,s.y+76),radius=38,fill=hx(acc)); x=X+28
        for c in t: s.d.text((x,s.y+17),c,font=f,fill=BASE); x+=s.d.textlength(c,font=f)+5
        s.y+=112
    def text(s,t,font,size,fill,lines=2,lh=1.12,gap=0):
        f,ls=wrap(t,font,size,lines)
        for l in ls: s.d.text((X,s.y),l,font=f,fill=fill); s.y+=int(f.size*lh)
        s.y+=gap
    def rule(s,acc): s.y+=22; s.d.rectangle((X,s.y,X+150,s.y+8),fill=hx(acc)); s.y+=46
def compose(kind,acc,blk,H,video):
    h=blk.y; bottom=H-420 if H>1500 else H-190; ty=bottom-h
    by=236 if H>1500 else 70
    if ty<by+62+16: raise SystemExit('slide text is %dpx too tall for the %dpx canvas - shorten it or split the slide'%(by+62+16-ty,H))
    im=bg(kind,acc,H,ty); im.alpha_composite(blk.im.crop((0,0,W,h+20)),(0,ty)); d=ImageDraw.Draw(im)
    f=F(HB,40); f2=F(RR,34); t="PanamaLive.Ai"
    pl=Image.new('RGBA',im.size,(0,0,0,0)); pd=ImageDraw.Draw(pl)
    pd.rounded_rectangle((X-26,by-14,X+d.textlength("PTY LIVE",font=f)+26,by+62),radius=38,fill=BASE[:3]+(205,))
    pd.rounded_rectangle((W-X-d.textlength(t,font=f2)-26,by-14,W-X+26,by+62),radius=38,fill=BASE[:3]+(205,))
    im.alpha_composite(pl); d=ImageDraw.Draw(im)
    d.text((X,by),"PTY",font=f,fill=WHITE)
    d.text((X+d.textlength("PTY ",font=f),by),"LIVE",font=f,fill=hx(acc))
    d.text((W-X-d.textlength(t,font=f2),by+6),t,font=f2,fill=(255,255,255,200))
    if not video: bars(im,1.7,hx(acc)[:3],H-70,80)
    return im
NB=22; bw=30; gp=(MW-NB*bw)/(NB-1)
def bars(fr,t,acc,BY,amp):
    d=ImageDraw.Draw(fr)
    for i in range(NB):
        h=20+(0.5+0.5*math.sin(t*6.5+i*0.9))*(0.5+0.5*math.sin(t*3.1+i*1.7+1.3))*amp
        x=X+i*(bw+gp); d.rounded_rectangle((x,BY-h,x+bw,BY),radius=8,fill=acc)
def gig(H,acc,day,genre,title,sub,rows):
    b=Blk(); b.pill(day,acc); b.text(genre.upper(),RB,40,hx(acc),1,1.0,22)
    b.text(title.upper(),HB,124,WHITE,2,1.06,12)
    if sub: b.text(sub,RR,50,(255,255,255,215),2,1.25)
    b.rule(acc)
    big=len(rows)==1
    for tm,l1,l2 in rows:
        b.text(tm,HB,128 if big else 84,hx(acc),1,1.18,6 if big else 0)
        b.text(l1,RB,58 if big else 50,WHITE,2,1.22); b.text(l2,RR,46 if big else 42,(255,255,255,200),2,1.25,0 if big else 26)
    return b
TC=205
def fit(t,font,size,w,floor=0.7):
    # Shrink to fit one line, but only so far: below ~70% the row stops being
    # readable on a phone, so the caller ellipsizes instead (see clip()).
    f=F(font,size); lo=int(size*floor)
    while MD.textlength(t,font=f)>w and f.size>lo: f=F(font,f.size-2)
    return f
def clip(t,f,w):
    if MD.textlength(t,font=f)<=w: return t
    while t and MD.textlength(t+'…',font=f)>w: t=t[:-1]
    return t.rstrip(' ·—-')+'…'
def day(acc,date,name,rows):
    b=Blk(); b.pill(date,acc); b.text(name.upper(),HB,116,WHITE,1,1.08); b.rule(acc)
    for tm,title,venue,ok in rows:
        y=b.y; b.d.text((X,y+3),tm,font=F(HB,38),fill=hx(acc) if ok else (255,255,255,150))
        f1=fit(title,RB,40,MW-TC); b.d.text((X+TC,y),clip(title,f1,MW-TC),font=f1,fill=WHITE)
        f2=fit(venue,RR,30,MW-TC); b.d.text((X+TC,y+50),clip(venue,f2,MW-TC),font=f2,fill=(255,255,255,190)); b.y+=98
    b.y+=8; b.text("Colored time: fully confirmed. For the rest, ask the venue.",RR,28,(255,255,255,150),1,1.3); b.text("Check Website: PanamaLive.AI",RB,28,(255,255,255,200),1,1.3)
    return 'vinyl',acc,b
def cover(H,wk):
    acc='#ff2e7e'; b=Blk(); b.pill(wk["range"],acc)
    b.text("PTY LIVE",HB,190,WHITE,1,1.04); b.text("MIX",HB,230,hx('#ffb020'),1,1.1); b.rule(acc)
    b.text("Your week in live music",RB,60,WHITE,1,1.25); b.text("Panama City",RR,50,(255,255,255,225),1,1.4)
    b.text(wk["cover_sub_reel"] if H>1500 else wk["cover_sub_carousel"],RR,46,(255,255,255,205),2,1.3)
    return 'vinyl',acc,b
def closing(H,wk):
    acc='#19d3c5'; b=Blk(); b.pill(wk["range"],acc)
    b.text("THE FULL",HB,190,WHITE,1,1.04); b.text("WEEK",HB,190,WHITE,1,1.14); b.rule(acc)
    b.text(f'{wk["total_listings"]} live music listings',RB,60,WHITE,1,1.5); b.text("PanamaLive.Ai",HB,120,hx(acc),1,1.25); b.text("#PTYLiveMix",RB,54,WHITE,1,1.1)
    return 'vinyl',acc,b
def slides(H,video,wk):
    S=[cover(H,wk)]; D=[5.6]
    for f in wk["features"]:
        S.append((f["art"],f["color"],gig(H,f["color"],f["day"],f["genre"],f["title"],f["sub"],[tuple(r) for r in f["rows"]]))); D.append(7.2 if len(f["rows"])==1 else 8.4)
    if video:
        for d in wk.get("days",[]):
            S.append(day(d["color"],d["date"],d["name"],[tuple(r) for r in d["rows"]])); D.append(8 if len(d["rows"])<=4 else 5+len(d["rows"]))
    S.append(closing(H,wk)); D.append(6.4)
    return [(compose(k,a,b,H,video),a) for k,a,b in S],D
def sheet(ims,w,h,path):
    sh=Image.new('RGB',(w*len(ims),h))
    for i,im in enumerate(ims): sh.paste(im.convert('RGB').resize((w,h),Image.LANCZOS),(i*w,0))
    sh.save(path)
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('week'); ap.add_argument('out'); ap.add_argument('music',nargs='?')
    ap.add_argument('--music-start',type=float,default=0,help='seconds into the track to start from')
    ap.add_argument('--keep-silent',action='store_true',help='keep the silent MP4 beside the one with music')
    a=ap.parse_args()
    wk=json.load(open(a.week,encoding='utf-8')); out=a.out; music=a.music
    os.makedirs(out,exist_ok=True); slug=wk["slug"]
    car,_=slides(1350,False,wk)
    for i,(im,_) in enumerate(car): im.convert('RGB').save(f'{out}/pty-live-mix-{slug}-carousel-{i+1:02d}.png')
    sheet([im for im,_ in car],360,450,f'{out}/check-carousel.png')
    H=1920; vid,durs=slides(H,True,wk); XF=0.45; rgb=[(im.convert('RGB'),hx(c)[:3]) for im,c in vid]
    sheet([im for im,_ in rgb],270,480,f'{out}/check-reel.png'); silent=f'{out}/pty-live-mix-{slug}-reel.mp4'
    p=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-shortest','-c:v','libx264','-preset','medium','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',silent],stdin=subprocess.PIPE)
    T=0
    for i,(im,acc) in enumerate(rgb):
        dur=durs[i]
        for k in range(int(dur*FPS)):
            t=k/FPS; fr=im.copy(); c=acc; rem=dur-t
            if i<len(rgb)-1 and rem<XF:
                m=1-rem/XF; m=m*m*(3-2*m); fr=Image.blend(fr,rgb[i+1][0],m); c=tuple(int(acc[j]*(1-m)+rgb[i+1][1][j]*m) for j in range(3))
            bars(fr,T+t,c,H-230,130); p.stdin.write(fr.tobytes())
        T+=dur
    p.stdin.close()
    if p.wait()!=0: raise SystemExit('ffmpeg failed while encoding the reel')
    print('reel: %.1fs, %d slides; carousel: %d slides'%(T,len(rgb),len(car)))
    if T>175: raise SystemExit('reel is %.0fs - keep it under three minutes'%T)
    if music:
        # -stream_loop so a short bed still covers a long week; the fade-out is
        # timed to the reel, not to the track.
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',silent,'-stream_loop','-1','-ss',str(a.music_start),'-i',music,'-map','0:v:0','-map','1:a:0','-c:v','copy','-af',f'atrim=0:{T},afade=t=in:st=0:d=0.3,afade=t=out:st={T-2}:d=2,loudnorm=I=-14:TP=-1.5','-c:a','aac','-b:a','192k','-ar','44100','-t',str(T),'-movflags','+faststart',f'{out}/pty-live-mix-{slug}-reel-with-music.mp4'],check=True)
        if not a.keep_silent: os.remove(silent)

"""어제 예상 점검 그림. 어제 글의 상방·횡보·하방 구간 위에 오늘 캔들 하나를 올린다.
사용:  python review_card.py spec.json out.png      (판정만 보려면 out.png 대신 --verdict)
spec.json 예:
 {"name":"삼성전자","day":"11월 5일(목)","unit":"원",
  "up":[228000,238000],"flat":[208000,228000],"down":[208000,195500],"plan":195500,
  "today":{"open":213000,"high":213500,"low":199800,"close":201500,"chg_pct":-7.57}}
down 은 [위, 아래] (1차, 2차) 순서. 판정은 이 파일이 기계적으로 정한다(글도 이 값을 그대로 쓴다).
"""
import json, sys
def verdict(s):
    t=s['today']; A,B=s['up']; C,D=s['flat']; E,F=s['down']
    v={}
    v['up']='닿음' if t['high']>=A else '안 열림'
    if t['low']<F: v['down']='이탈'
    elif t['low']<=E: v['down']='구간 안' if t['close']<=E else '저가만 닿음'
    else: v['down']='안 닿음'
    lo_out=t['low']<C; hi_out=t['high']>D
    v['flat']='맞음' if not(lo_out or hi_out) else ('하단 이탈' if lo_out and not hi_out else ('상단 이탈' if hi_out and not lo_out else '양쪽 이탈'))
    if s.get('plan') is not None: v['plan']='닿음' if t['low']<=s['plan'] else '안 닿음'
    return v
def fmt(x,u): return f"{x:,.0f}"+("" if u=="포인트" else "") + u
def draw(s,out):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    names={f.name for f in fm.fontManager.ttflist}
    for c in ['Noto Sans CJK KR','NanumGothic','Nanum Gothic','Noto Sans KR','Malgun Gothic','AppleGothic','Noto Sans CJK JP']:
        if c in names: plt.rcParams['font.family']=c; break
    else: raise SystemExit('한글 글꼴이 없어요(fonts-noto-cjk 또는 fonts-nanum 설치 필요)')
    plt.rcParams['axes.unicode_minus']=False
    t=s['today']; u=s['unit']; A,B=s['up']; C,D=s['flat']; E,F=s['down']; v=verdict(s)
    vals=[t['high'],t['low'],A,B,C,D,E,F]+([s['plan']] if s.get('plan') else [])
    lo,hi=min(vals),max(vals); pad=(hi-lo)*0.06; lo-=pad*2; hi+=pad
    fig=plt.figure(figsize=(10.8,9.6),dpi=100); fig.patch.set_facecolor('white')
    fig.text(0.06,0.945,f"{s['name']}  {s['day']} 어제 예상 점검",fontsize=24,fontweight='bold',va='center')
    sub=f"어제 구간 vs 오늘 시가 {fmt(t['open'],u)} · 고가 {fmt(t['high'],u)} · 저가 {fmt(t['low'],u)} · 종가 {fmt(t['close'],u)} ({t['chg_pct']:+.2f}%)"
    fig.text(0.06,0.905,sub,fontsize=12,color='#666',va='center')
    fig.text(0.94,0.945,'버거대왕 국장 레이더',fontsize=11,color='#999',ha='right',va='center')
    ax=fig.add_axes([0.06,0.27,0.80,0.60]); ax.set_xlim(0,1); ax.set_ylim(lo,hi)
    for sp in ['top','right','left']: ax.spines[sp].set_visible(False)
    ax.set_xticks([]); ax.yaxis.tick_right(); ax.tick_params(axis='y',labelsize=11,colors='#555')
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y,_:f"{y:,.0f}"))
    ax.grid(axis='y',color='#eee',lw=0.8)
    def band(a,b,col,label,x0=0.0,x1=0.62):
        ax.axhspan(min(a,b),max(a,b),xmin=x0,xmax=x1,color=col,alpha=0.22,lw=0)
        for y in (a,b): ax.plot([x0,x1],[y,y],color=col,lw=1.2,ls='--')
        ax.text(0.01,(a+b)/2,f"{label}\n{fmt(min(a,b),u)} — {fmt(max(a,b),u)}",va='center',fontsize=13,color=col,fontweight='bold')
    band(A,B,'#e03131','어제 상방')
    band(C,D,'#868e96','어제 횡보')
    band(F,E,'#1c6fe0','어제 하방')
    if s.get('plan'): 
        ax.plot([0,0.62],[s['plan']]*2,color='#2b8a3e',lw=1.6,ls=':'); ax.text(0.615,s['plan'],f" 어제 계획 {fmt(s['plan'],u)}",va='bottom',ha='right',fontsize=11,color='#2b8a3e')
    cx=0.80; up=t['close']>=t['open']; col='#e03131' if up else '#1c6fe0'
    ax.plot([cx,cx],[t['low'],t['high']],color=col,lw=3)
    ax.add_patch(plt.Rectangle((cx-0.05,min(t['open'],t['close'])),0.10,abs(t['close']-t['open']) or (hi-lo)*0.002,color=col))
    for y,l,dy in [(t['high'],f"고가 {fmt(t['high'],u)}",1),(t['low'],f"저가 {fmt(t['low'],u)}",-1)]:
        ax.text(cx,y,l,ha='center',va='bottom' if dy>0 else 'top',fontsize=11,color='#333')
    ax.text(cx+0.06,t['close'],f" 종가 {fmt(t['close'],u)}",va='center',ha='left',fontsize=11,color=col,fontweight='bold')
    ax.text(cx,-0.02,'오늘',ha='center',va='top',fontsize=12,color='#888',transform=ax.get_xaxis_transform())
    rows=[('상방',v['up']),('하방',v['down']),('횡보',v['flat'])]+([('어제 계획 가격',v['plan'])] if 'plan' in v else [])
    good={'안 열림','구간 안','맞음','닿음'}
    x=0.06
    for k,val in rows:
        okc='#2b8a3e' if (val in good and not(k=='어제 계획 가격')) else ('#c92a2a' if val in ('이탈','하단 이탈','상단 이탈','양쪽 이탈') else '#555')
        fig.text(x,0.145,k,fontsize=12,color='#888',va='center'); fig.text(x,0.095,val,fontsize=20,fontweight='bold',color=okc,va='center')
        x+=0.22
    fig.text(0.06,0.035,'판정 기준: 상방은 오늘 고가가 어제 상방 아래값에 닿았는지, 하방은 오늘 저가·종가가 어제 하방 구간 안인지, 횡보는 오늘 고가·저가가 구간 안인지',fontsize=9.5,color='#999')
    fig.savefig(out,facecolor='white'); plt.close(fig)
if __name__=='__main__':
    s=json.load(open(sys.argv[1],encoding='utf-8'))
    if sys.argv[2]=='--verdict': print(json.dumps(verdict(s),ensure_ascii=False))
    else: draw(s,sys.argv[2]); print(json.dumps(verdict(s),ensure_ascii=False))

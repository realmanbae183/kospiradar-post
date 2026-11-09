"""블로그 글 렌더러. render(name,title,blocks,tags) -> OUT/name.html/.txt/.md + OUT/img/name/. blocks: ("key"|"topic"|"p"|"sky"|"hr"|"img",text[,label]).
환경변수 BLOG_OUT 으로 출력 폴더 지정. 서식 규칙은 예약 작업 지시문 참고."""
import sys,html,io,base64,os
from PIL import Image
DIS="이 글은 개인 기록일 뿐 투자 권유가 아닙니다. 모든 투자 판단과 책임은 본인에게 있습니다.."
FF="font-family:'Nanum Gothic',sans-serif;"
K=os.environ.get('BLOG_K','.'); R=os.environ.get('BLOG_R','.'); OUT=os.environ.get('BLOG_OUT','./out'); os.makedirs(OUT,exist_ok=True)
def emb(path):
    im=Image.open(path).convert("RGB")
    if im.width>900: im=im.resize((900,int(im.height*900/im.width)))
    b=io.BytesIO(); im.save(b,"JPEG",quality=82); return "data:image/jpeg;base64,"+base64.b64encode(b.getvalue()).decode()
def render(name,title,blocks,tags):
    import shutil
    cnt=[0]; t=[]
    SP='<p style="margin:0;"><span style="font-size:15px;font-weight:normal;">&nbsp;</span></p>'
    def lines(x,size,color="#000",bold=False,bg=None,center=False):
        out=[]
        for ln in x.split("\n"):
            st=f"font-size:{size}px;color:{color};font-weight:{'bold' if bold else 'normal'};font-style:normal;"+(f"background-color:{bg};" if bg else "")
            inner=f'<span style="{st}">'+html.escape(ln)+'</span>'
            out.append(f'<p style="margin:0;{"text-align:center;" if center else ""}">{inner}</p>')
        return "\n".join(out)
    h=[f'<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title><body style="max-width:760px;margin:30px auto;font-family:\'Nanum Gothic\',sans-serif;">']
    h.append('<p style="margin:0;"><span style="font-size:12px;color:#c00;">▼ 제목칸에 붙여넣기 (아래 한 줄)</span></p>')
    h.append(f'<p style="margin:0;"><span style="font-size:22px;font-weight:bold;">{html.escape(title)}</span></p>')
    h.append('<p style="margin:0;"><span style="font-size:12px;color:#c00;">▼ 여기서부터 본문 복사 (맨 아래 태그까지)</span></p><hr>')
    h.append('<div id="post">')
    for b in blocks:
        k=b[0]; x=b[1] if len(b)>1 else ""
        if k=="key": h+= [lines(x,24,bold=True,bg="#fff59d"),SP]; t.append(x)
        elif k=="topic": h+= [lines(x,19,bold=True,bg="#c8f7c5"),SP]; t.append(x)
        elif k=="p": h+= [lines(x,15),SP]; t.append(x)
        elif k=="sky": h+= [lines(x,15,color="#2b8fd9"),SP]; t.append(x)
        elif k=="hr": h+= [SP,lines("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",13,color="#999"),SP]; t.append("")
        elif k=="img":
            os.makedirs(f"{OUT}/img/{name}",exist_ok=True); cnt[0]+=1
            ext=os.path.splitext(x)[1]; fn=f"{cnt[0]:02d}-{b[2].replace(' ','-')}{ext}"; shutil.copy(x,f"{OUT}/img/{name}/{fn}")
            h+= [lines(f"【 사진 자리 · {b[2]} 】  ({fn})",14,color="#777",bold=True,center=True),SP]; t.append(f"[사진 자리 · {b[2]}]")
    h+= [lines(DIS,15),SP,lines(tags,13,color="#555"),'</div></body>']
    open(f"{OUT}/{name}.html","w").write("\n".join(h))
    body="\n\n".join(s for s in t if s)
    open(f"{OUT}/{name}.txt","w").write(f"{title}\n\n{body}\n\n{DIS}\n\n{tags}\n")
    open(f"{OUT}/{name}.md","w").write(f"{title}\n\n{body}\n\n{DIS}\n")
    print(name,len(body),len(tags.split()),sum(b[0]=="key" for b in blocks))

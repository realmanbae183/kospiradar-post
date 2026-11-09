"""usage: python3 tools/build_paste_page.py <blog/날짜 폴더> "<M월 D일>" <출력.html>
daily-1-summary / daily-2-forecast / daily-3-study 의 .html 3개를 읽어 '제목 복사 / 본문 전체 복사' 버튼이 있는 붙여넣기 페이지를 만든다."""
import sys,re,html
d,date,out=sys.argv[1:4]
page=open(__file__.rsplit("/",1)[0]+"/paste_page_template.html").read().replace("@@DATE@@",date)
for i,n in enumerate(["1-summary","2-forecast","3-study"]):
    s=open(f"{d}/daily-{n}.html").read()
    title=html.unescape(re.search(r"<title>(.*?)</title>",s).group(1))
    body=s[s.index('<div id="post">')+len('<div id="post">'):s.rindex('</div></body>')]
    page=page.replace("@@TITLE%d@@"%i,html.escape(title)).replace("@@BODY%d@@"%i,body)
open(out,"w").write(page)

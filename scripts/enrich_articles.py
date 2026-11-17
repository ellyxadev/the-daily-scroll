#!/usr/bin/env python3
"""Enrich recent articles with publisher metadata and (optionally) Dutch AI summaries.

No API key: only source media and a transparent RSS-description fallback.
Set OPENAI_API_KEY in GitHub Actions Secrets for automatic editorial summaries.
"""
import json, os, re, html, time
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'data/articles.json'
ALLOWED={'www.theguardian.com','theguardian.com','techcrunch.com','www.techcrunch.com',
         'theverge.com','www.theverge.com','www.vrt.be','vrt.be'}
class Metadata(HTMLParser):
    def __init__(self):
        super().__init__();self.meta={};self.links=[];self.images=0;self.videos=0;self.title=''
        self.in_title=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='meta':
            key=a.get('property') or a.get('name')
            if key and a.get('content'):self.meta[key.lower()]=a['content']
        if tag=='img':self.images+=1
        if tag in ('video','iframe') and ('video' in a.get('src','') or tag=='video'):self.videos+=1
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='title':self.in_title=True
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,d):
        if self.in_title:self.title+=d

def safe_url(value,base='',image=False):
    if not value:return ''
    u=urlparse(urljoin(base,value))
    if u.scheme!='https' or not u.netloc:return ''
    if u.hostname in ('localhost','127.0.0.1'):return ''
    if image and not re.search(r'\.(jpg|jpeg|png|webp)(?:$|\?)',u.path+'?'+u.query,re.I):
        # Many publisher image services omit file extensions.
        if 'guim.co.uk' not in (u.hostname or '') and 'techcrunch.com' not in (u.hostname or ''):return ''
    return u.geturl()

def article_metadata(a):
    url=a.get('url','')
    if urlparse(url).hostname not in ALLOWED:return {}
    try:
        req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; DailyScrollReader/1.0)'})
        with urlopen(req,timeout=12) as f:
            raw=f.read(380_000)
            content_type=f.headers.get('Content-Type','')
        if 'html' not in content_type:return {}
        parser=Metadata();parser.feed(raw.decode('utf-8','replace'))
        m=parser.meta
        image=safe_url(m.get('og:image') or m.get('twitter:image'),url,True)
        media_video=m.get('og:video') or m.get('twitter:player','')
        video_url=safe_url(media_video,url) if media_video else ''
        # Prefer publisher-linked video evidence, not generic website nav links.
        youtube=next((safe_url(x,url) for x in parser.links if 'youtube.com/watch' in x or 'youtu.be/' in x),'')
        description=html.unescape(m.get('og:description') or m.get('description') or '')[:650]
        result={'image_url':image,'has_images':parser.images>0 or bool(image),
                'has_video':bool(video_url or youtube or parser.videos)}
        if video_url or youtube:result['video_url']=video_url or youtube
        if description:result['publisher_excerpt']=re.sub(r'\s+',' ',description)
        # Some publishers block automated access; no invented media declarations.
        return result
    except Exception as e:
        print('Could not inspect:',url,str(e)[:100]);return {}

def summarize_with_ai(a):
    key=os.getenv('OPENAI_API_KEY')
    if not key:return {}
    source=a.get('publisher_excerpt') or a.get('description') or ''
    if len(source)<50:return {}
    # Model only sees publisher excerpt, NOT full article; always label accurately.
    prompt=('Maak een toegankelijke Katrijn-proof Nederlandse tekst op basis van uitsluitend de '
            'onderstaande bronbeschrijving. Leg in drie tot vijf zinnen feitelijk uit waar het over '
            'gaat, waarom dit verrassend of interessant kan zijn, en geef een herkenbaar voorbeeld '
            'alleen als het een duidelijk hypothetisch voorbeeld is. Verzin niets over het volledige '
            'artikel. Als belangrijke details ontbreken, benoem dat. Geen sensatie, geen hype. '
            'Antwoord uitsluitend met JSON {"summary_nl":"...","takeaway_nl":"..."}.\n'
            'Titel: '+a.get('title','')+'\nBron: '+a.get('source','')+'\nBeschrijving: '+source)
    payload={'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),
             'input':[{'role':'user','content':prompt}]}
    from urllib.error import HTTPError
    try:
        req=Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),
            headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=30) as f:r=json.load(f)
        txt=''.join(c.get('text','') for o in r.get('output',[])
            for c in o.get('content',[]) if c.get('type')=='output_text')
        obj=json.loads(txt.strip().removeprefix('```json').removesuffix('```').strip())
        if isinstance(obj.get('summary_nl'),str) and isinstance(obj.get('takeaway_nl'),str):
            return {'summary_nl':obj['summary_nl'][:1200],
                    'takeaway_nl':obj['takeaway_nl'][:240],'summary_basis':'excerpt'}
    except Exception as e:print('AI enrichment unavailable:',str(e)[:120])
    return {}

def main():
    if not FILE.exists():return
    data=json.loads(FILE.read_text('utf-8'))
    processed=0
    for a in data.get('articles',[]):
        if processed>=12:break
        if a.get('media_checked') and a.get('summary_nl'):continue
        if not a.get('media_checked'):
            m=article_metadata(a)
            if m:a.update(m)
            a['media_checked']=True
        # Never overwrite editorial summaries based on full articles.
        if not a.get('summary_nl'):
            a.update(summarize_with_ai(a))
        processed+=1
    if processed:
        FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('Enriched:',processed,'AI enabled:',bool(os.getenv('OPENAI_API_KEY')))
if __name__=='__main__':main()

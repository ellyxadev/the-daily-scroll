#!/usr/bin/env python3
"""Add recent RSS stories to the archival feed. Standard library only.

This is a lightweight, transparent curator, not an LLM recommender.
RSS dates and links are checked; the source description may be imperfect.
"""
from __future__ import annotations
import datetime as dt
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from xml.etree import ElementTree as ET
from pathlib import Path
import json, re, html, hashlib, os, sys

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/articles.json'
TZ=ZoneInfo('Europe/Brussels')
NOW=dt.datetime.now(dt.timezone.utc)
LOCAL=NOW.astimezone(TZ)
# Cron fires in both winter and summer UTC candidates; only retain 6am Brussels run.
if os.environ.get('GITHUB_ACTIONS') and os.environ.get('GITHUB_EVENT_NAME')=='schedule' and LOCAL.hour != 6:
    print('Not 06:xx in Brussels:',LOCAL.isoformat());sys.exit(0)

FEEDS=[
 ('The Guardian','https://www.theguardian.com/lifeandstyle/rss','Lifestyle'),
 ('The Guardian','https://www.theguardian.com/commentisfree/rss','Columns'),
 ('The Guardian','https://www.theguardian.com/culture/rss','Culture'),
 ('TechCrunch','https://techcrunch.com/feed/','Technology'),
 ('The Verge','https://www.theverge.com/rss/index.xml','Technology'),
 ('VRT NWS','https://www.vrt.be/vrtnws/nl.rss.articles.xml','Belgium'),
]
POSITIVE={
 'Humor': ['funny','humour','humor','comedy','laugh','ridiculous','absurd','cat','cats','pet','pets','silly','awkward','column','winter','meme','ghosting','cartoon','grappig','humor','kat','column'],
 'Women':['women','woman','girlhood','feminism','beauty','makeup','make-up','relationships','marriage','pressure','gender','vrouwen','vrouw','schoonheid','huwelijk'],
 'AI':['artificial intelligence','ai ',' ai','chatgpt','claude','robot','agents','openai','machine learning','screen time','audiobook','technology'],
 'Cultuur':['musical','music','movie','cinema','film','theatre','theater','pop culture','lady gaga','charli xcx','podcast','books','boek','muziek','streaming'],
 'Cosy':['cozy','cosy','gaming','video game','palia','loftia','nintendo','animal crossing','simulation'],
 'Welzijn':['wellbeing','wellness','mental health','self-care','health','hobby','friendship','burnout','gastric bypass','bariatric','well-being','gezondheid','welzijn'],
 'Marketing':['marketing','campaign','advertising','branding','social media','creators','crm','customer experience'],
 'Ontdekken':['science','discovery','psychology','study','research','why','mystery','wetenschap','onderzoek','ontdekking'],
}
NEGATIVE=['murder','killed','rape','death toll','shooting','war crimes','assault','terror','suicide','child abuse','violent','pornography','political scandal']
ALLOW={'theguardian.com','www.theguardian.com','techcrunch.com','www.techcrunch.com','theverge.com','www.theverge.com','vrt.be','www.vrt.be'}

def text_clean(raw):
    raw=re.sub(r'<[^>]+>',' ',raw or '')
    return ' '.join(html.unescape(raw).split())

def norm_url(url):
    u=urlparse(url)
    if u.scheme!='https' or u.hostname not in ALLOW:return ''
    keep=[(k,v) for k,v in parse_qsl(u.query) if k not in {'utm_source','utm_medium','utm_campaign','utm_content','ref','fbclid'}]
    return urlunparse((u.scheme,u.netloc,u.path,'',urlencode(keep),''))

def timestamp(raw):
    try:
        d=parsedate_to_datetime(raw)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        try:return dt.datetime.fromisoformat(raw.replace('Z','+00:00')).astimezone(dt.timezone.utc)
        except Exception:return None

def category_for(title,desc,kind):
    content=(title+' '+desc).lower()
    scores={k:sum(2 if word in title.lower() else 1 for word in keys if word in content) for k,keys in POSITIVE.items()}
    if kind=='Columns':scores['Humor']+=1
    if kind=='Technology':scores['AI']+=1
    if kind=='Culture':scores['Cultuur']+=1
    if kind=='Belgium':scores['Ontdekken']+=1
    category=max(scores,key=scores.get)
    if scores[category]<1:return None
    return category

def parse_feed(raw,source,kind):
    tree=ET.fromstring(raw)
    if tree.tag.endswith('rss') or tree.find('channel') is not None:
        for i in tree.findall('.//channel/item'):
            t=text_clean(i.findtext('title') or '')
            link=(i.findtext('link') or '').strip()
            date=timestamp(i.findtext('pubDate') or '')
            description=text_clean(i.findtext('description') or '')
            creator=i.findtext('{http://purl.org/dc/elements/1.1/}creator') or source
            yield t,link,date,description,text_clean(creator)
    else:
        ns='{http://www.w3.org/2005/Atom}'
        for i in tree.findall('.//'+ns+'entry'):
            t=text_clean(i.findtext(ns+'title') or '')
            link=next((e.attrib.get('href','') for e in i.findall(ns+'link') if e.attrib.get('rel','alternate') in ('alternate','')), '')
            date=timestamp(i.findtext(ns+'published') or i.findtext(ns+'updated') or '')
            description=text_clean(i.findtext(ns+'summary') or '')
            author=i.findtext(ns+'author/'+ns+'name') or source
            yield t,link,date,description,author

old=json.loads(DATA.read_text('utf-8')) if DATA.exists() else {'articles':[]}
articles={s['id']:s for s in old.get('articles',[]) if s.get('id') and s.get('url')}
new=[]
for source,url,kind in FEEDS:
    try:
        req=Request(url,headers={'User-Agent':'DailyScrollPersonalReader/1.0 (+RSS; no scraping)'})
        with urlopen(req, timeout=18) as resp:xml=resp.read(2_000_000)
        added=0
        for title,link,published,description,author in parse_feed(xml,source,kind):
            safe=norm_url(link)
            if not safe or not title or not published:continue
            age=NOW-published.astimezone(dt.timezone.utc)
            if not dt.timedelta(0)<=age<=dt.timedelta(days=7):continue
            low=(title+' '+description).lower()
            if any(term in low for term in NEGATIVE):continue
            cat=category_for(title,description,kind)
            if cat is None:continue
            ident=hashlib.sha256(safe.encode()).hexdigest()[:16]
            if ident in articles:continue
            day=published.astimezone(TZ).date().isoformat()
            # Keep source-provided summaries; do not represent this as a hand-written review.
            excerpt=description[:240].rsplit(' ',1)[0].rstrip(' .,;:')+'…' if len(description)>240 else description
            if not excerpt:excerpt='Een nieuwe publicatie over '+cat.lower()+'. Klik om zelf te ontdekken of dit je aanspreekt.'
            mood={ 'Humor':['laugh','relax'], 'Women':['relate','learn'], 'AI':['learn'], 'Cultuur':['relax','learn'], 'Cosy':['relax'], 'Welzijn':['relate','relax'], 'Marketing':['learn'], 'Ontdekken':['learn'] }[cat]
            new.append({'id':ident,'title':title[:180],'description':excerpt,'category':cat,'kind':'Column' if kind=='Columns' else 'Artikel','author':author[:100],'date':day,'minutes':max(2,min(12,round(len(description.split())/45)+3)),'url':safe,'source':source,'moods':mood})
            added+=1
        print(source,':',added,'new candidates')
    except Exception as e:
        print('Feed unavailable:',source,str(e)[:180])

# Limit new intake to keep the feed readable; balance categories as much as possible.
# RSS does not tell us whether a page is paywalled. Never claim it's free.
by_cat={}
for item in new:
    by_cat.setdefault(item['category'],[]).append(item)
for k,v in by_cat.items():
    # At most 4 new entries of a topic per run (keeps AI/news from crowding out columns).
    for item in v[:4]:articles[item['id']]=item

out={'last_updated':LOCAL.isoformat(timespec='seconds'),'articles':sorted(articles.values(),key=lambda x:(x['date'],x['id']),reverse=True)}
if out['articles']:
    DATA.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
print('Archived:',len(out['articles']),'Total; added:',len(out['articles'])-len(old.get('articles',[])))

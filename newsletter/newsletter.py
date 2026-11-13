#!/usr/bin/env python3
"""Hourly AI News -> Telegram (The Unstoppable Firehose Edition)"""

import html as htmllib
import io
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
try:
    from PIL import Image
except Exception:
    Image = None

# ----------------------------------------------------------------------------
# CONFIG (Firehose Mode)
# ----------------------------------------------------------------------------
DEFAULT_KEYWORDS = ("artificial intelligence, AI, LLM, OpenAI, Anthropic, Gemini, Claude, ChatGPT, DeepSeek, Nvidia, AI agents, machine learning")
KEYWORDS = [k.strip() for k in (os.getenv("KEYWORDS") or DEFAULT_KEYWORDS).split(",") if k.strip()]

HOURS = int(os.getenv("HOURS_BACK") or 4)         # Look back 4 hours to ensure we catch everything
MAX_POSTS = int(os.getenv("MAX_POSTS") or 100)    # Post up to 100 per run
MIN_SCORE = int(os.getenv("MIN_SCORE") or 0)      # 0 = Accept everything
MAX_EVAL = int(os.getenv("MAX_EVAL") or 200)      
DRY_RUN = os.getenv("DRY_RUN") == "1"
REQUIRE_IMAGE = False                             # FORCE FALSE: Never drop a story just because it lacks an image

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")       
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GH_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN", "")

STATE_PATH = os.getenv("STATE_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "posted.json")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = [m for m in dict.fromkeys([os.getenv("GROQ_MODEL", "").strip(), "openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]) if m]
_groq = {"idx": 0, "disabled": False, "discovered": False}

UA = "Mozilla/5.0 (compatible; ai-news-bot/6.0)"
NOW = datetime.now(timezone.utc)
SINCE = NOW - timedelta(hours=HOURS)

# ----------------------------------------------------------------------------
# SOURCES
# ----------------------------------------------------------------------------
FEEDS = [
    ("OpenAI", "https://openai.com/news/rss.xml", 95),
    ("Anthropic", "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml", 95),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", 90),
    ("Google AI", "https://blog.google/innovation-and-ai/technology/ai/rss/", 85),
    ("Google Research", "https://research.google/blog/rss/", 80),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", 85),
    ("Mistral AI", "https://mistral.ai/news/rss", 85),
    ("Microsoft AI", "https://news.microsoft.com/source/topics/ai/feed/", 80),
    ("Meta Engineering", "https://engineering.fb.com/feed/", 75),
    ("The Decoder", "https://the-decoder.com/feed/", 80),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", 75),
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/", 75),
    ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed", 75),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", 70),
    ("Ars Technica", "https://arstechnica.com/ai/feed/", 70),
    ("MIT News", "https://news.mit.edu/rss/topic/artificial-intelligence2", 68),
    ("Wired", "https://www.wired.com/feed/tag/ai/latest/rss", 68),
    ("AWS ML Blog", "https://aws.amazon.com/blogs/machine-learning/feed/", 65),
    ("NVIDIA Tech Blog", "https://developer.nvidia.com/blog/feed", 65),
    ("MarkTechPost", "https://www.marktechpost.com/feed/", 60),
]

def log(msg):
    for secret in (TG_TOKEN, GROQ_KEY, NEWSAPI_KEY, GH_TOKEN):
        if secret: msg = str(msg).replace(secret, "***")
    print(msg, file=sys.stderr, flush=True)

# ----------------------------------------------------------------------------
# HELPERS & PARSERS
# ----------------------------------------------------------------------------
TAG = re.compile(r"<[^>]+>")
def clean(s): return re.sub(r"\s+", " ", TAG.sub(" ", htmllib.unescape(str(s or "")))).strip()
def clip(s, n): return re.sub(r"\s+\S*$", "", s[: n - 1]) + "…" if len(s) > n else s

def parse_dt(s):
    if not s: return None
    try:
        if re.match(r"\d{4}-\d{2}-\d{2}", s): d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else: d = parsedate_to_datetime(s)
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except: return None

def recent(d): return d is not None and d >= SINCE
def host(u):
    m = re.match(r"https?://(?:www\.)?([^/]+)", u or "")
    return m.group(1) if m else ""

def clean_url(u):
    try:
        p = urlsplit(str(u).strip())
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref", "source")]
        return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), ""))
    except: return str(u or "")

def ukey(u):
    p = urlsplit(clean_url(u))
    return (p.netloc + p.path).rstrip("/").lower()

def local(tag): return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""
def child_text(e, *names):
    for c in e:
        if local(c.tag) in names and (c.text or "").strip(): return c.text.strip()
    return ""

def entry_link(e):
    for c in e:
        if local(c.tag) == "link":
            if c.get("href") and c.get("rel", "alternate") == "alternate": return c.get("href")
            if (c.text or "").strip(): return c.text.strip()
    return ""

def entry_image(e, html_blob):
    for c in e:
        k = local(c.tag)
        if k in ("content", "thumbnail") and c.get("url") and (k == "thumbnail" or "image" in (c.get("type", "") + c.get("medium", "image"))): return c.get("url")
        if k == "enclosure" and c.get("url") and c.get("type", "").startswith("image"): return c.get("url")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', htmllib.unescape(html_blob or ""), re.I)
    return m.group(1) if m else ""

def http_get(url, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", UA)
    try:
        r = requests.get(url, headers=headers, timeout=15, **kwargs)
        r.raise_for_status()
        return r
    except Exception:
        return None

def make_item(title, url, excerpt, source, outlet, published_at, source_weight, engagement=0, repo=None, image=""):
    return {"title": title, "url": clean_url(url), "excerpt": excerpt, "source": source, "outlet": outlet, "published_at": published_at, "source_weight": source_weight, "engagement": engagement, "repo": repo, "image": image}

# ----------------------------------------------------------------------------
# FETCHERS
# ----------------------------------------------------------------------------
def fetch_feed(name, url, weight):
    out = []; r = http_get(url)
    if not r: return name, out
    try: root = ET.fromstring(r.content)
    except: return name, out
    for e in root.iter():
        if local(e.tag) not in ("item", "entry"): continue
        title, link, pub = clean(child_text(e, "title")), clean_url(entry_link(e)), parse_dt(child_text(e, "pubDate", "published", "updated", "date"))
        body = child_text(e, "encoded", "content") or child_text(e, "description", "summary")
        if title and link.startswith("http") and recent(pub):
            out.append(make_item(title, link, clean(body)[:3000], name, host(link) or name, pub, weight, image=entry_image(e, body)))
    return name, out

def fetch_arxiv():
    out = []; q = " OR ".join(f'all:"{k}"' for k in KEYWORDS[:3])
    r = http_get("https://export.arxiv.org/api/query", params={"search_query": q, "start": 0, "max_results": 30, "sortBy": "submittedDate", "sortOrder": "descending"})
    if not r: return "arXiv", out
    try: root = ET.fromstring(r.content)
    except: return "arXiv", out
    for e in root.iter():
        if local(e.tag) != "entry": continue
        title, link, pub, summary = clean(child_text(e, "title")), clean_url(child_text(e, "id")), parse_dt(child_text(e, "published")), clean(child_text(e, "summary"))[:3000]
        if title and link.startswith("http") and recent(pub): out.append(make_item(title, link, summary, "arXiv", "arXiv", pub, 80))
    return "arXiv", out

def fetch_hackernews():
    out = []; q = " OR ".join(f'"{k}"' for k in KEYWORDS[:3])
    r = http_get("https://hn.algolia.com/api/v1/search", params={"query": q, "tags": "story", "numericFilters": f"created_at_i>{int(SINCE.timestamp())}", "hitsPerPage": 40})
    if not r: return "Hacker News", out
    for h in r.json().get("hits", []):
        if h.get("title") and h.get("url"):
            out.append(make_item(clean(h["title"]), h["url"], "", "HackerNews", host(h["url"]) or "Hacker News", datetime.fromtimestamp(h.get("created_at_i", 0), timezone.utc), 70, h.get("points") or 0))
    return "Hacker News", out

def fetch_github():
    out, seen = [], set(); headers = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN: headers["Authorization"] = f"Bearer {GH_TOKEN}"
    for kw in KEYWORDS[:2]:
        r = http_get("https://api.github.com/search/repositories", headers=headers, params={"q": f"{kw} created:>{SINCE.strftime('%Y-%m-%d')}", "sort": "stars", "order": "desc", "per_page": 15})
        if r:
            for repo in r.json().get("items", []):
                created = parse_dt(repo.get("created_at"))
                if repo["full_name"] not in seen and recent(created) and (repo.get("stargazers_count") or 0) >= 15:
                    seen.add(repo["full_name"]); desc = clean(repo.get("description"))
                    out.append(make_item(repo["full_name"] + (" - " + desc if desc else ""), repo["html_url"], desc or repo["full_name"], "GitHub", "GitHub", created, 55, repo.get("stargazers_count") or 0, repo=repo["full_name"], image="https://opengraph.githubassets.com/1/" + repo["full_name"]))
    return "GitHub", out

def fetch_newsapi():
    out = []
    if not NEWSAPI_KEY: return "NewsAPI", out
    r = http_get("https://newsapi.org/v2/everything", headers={"X-Api-Key": NEWSAPI_KEY}, params={"q": " OR ".join(f'"{k}"' for k in KEYWORDS[:5]), "from": SINCE.strftime("%Y-%m-%dT%H:%M:%SZ"), "sortBy": "publishedAt", "language": "en", "pageSize": 30})
    if not r: return "NewsAPI", out
    for a in r.json().get("articles", []):
        pub = parse_dt(a.get("publishedAt"))
        if a.get("title") and a["title"] != "[Removed]" and a.get("url") and recent(pub):
            out.append(make_item(clean(a["title"]), a["url"], clean(a.get("description") or a.get("content") or a["title"])[:3000], "NewsAPI", (a.get("source") or {}).get("name") or host(a["url"]), pub, 60, image=a.get("urlToImage") or ""))
    return "NewsAPI", out

def gather():
    jobs = [fetch_arxiv, fetch_hackernews, fetch_github, fetch_newsapi] + [(lambda n=n, u=u, w=w: fetch_feed(n, u, w)) for n, u, w in FEEDS]
    items = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for fut in [pool.submit(j) for j in jobs]:
            try:
                name, got = fut.result(); log(f" {name}: {len(got)} recent stories"); items += got
            except Exception as e: log(f"Source crash: {e}")
    return items

# ----------------------------------------------------------------------------
# ENRICHMENT
# ----------------------------------------------------------------------------
def rank(items):
    kws = [k.lower() for k in KEYWORDS]
    for j in items:
        s = j["source_weight"]
        s -= min(max(0.0, (NOW - j["published_at"]).total_seconds() / 3600) * 1.5, 18)
        text = (j["title"] + " " + j.get("excerpt", "")).lower()
        s += min(sum(text.count(k) for k in kws) * 4, 16)
        s += min(math.log1p(j.get("engagement") or 0) * 3, 12)
        j["score"] = s
    return sorted(items, key=lambda j: j["score"], reverse=True)

OG = re.compile(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)
OG2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']', re.I)
TWITTER = re.compile(r'<meta[^>]+(?:property|name)=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)

def find_og_image(page):
    for rx in (OG, OG2, TWITTER):
        m = rx.search(page)
        if m: return m.group(1)
    return ""

def page_text(page):
    page = re.sub(r"(?is)<(script|style|noscript|svg|iframe|head)[^>]*>.*?</\1>", " ", page)
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", page)
    paras = [clean(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", m.group(1) if m else page)]
    return " ".join(p for p in paras if len(p) >= 60)[:4000]

def enrich_and_download_image(j):
    j["text"] = j["excerpt"]
    j["image_bytes"] = None
    
    if j["source"] != "arXiv":
        r = http_get(j["url"], headers={"Accept": "text/html"}, timeout=10)
        if r:
            page = r.text[:400000]
            body = page_text(page)
            if len(body) > len(j["text"]): j["text"] = body
            if not j.get("image"):
                found = find_og_image(page)
                j["image"] = urljoin(j["url"], htmllib.unescape(found)) if found else ""

    if j.get("image") and j["image"].startswith("http") and not re.search(r"\.svg(\?|$)", j["image"], re.I):
        try:
            r = requests.get(j["image"], headers={"User-Agent": UA, "Referer": j["url"]}, timeout=10)
            if r.ok:
                data = r.content
                if Image is not None:
                    im = Image.open(io.BytesIO(data))
                    if im.size[0] > 300 and im.size[1] > 150:
                        im = im.convert("RGB")
                        im.thumbnail((1280, 1280))
                        buf = io.BytesIO()
                        im.save(buf, "JPEG", quality=85)
                        j["image_bytes"] = buf.getvalue()
                else:
                    j["image_bytes"] = data
        except Exception:
            pass
    return j

# ----------------------------------------------------------------------------
# AI SUMMARY & TELEGRAM
# ----------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the editor of a tech news Telegram channel. Return exactly ONE valid JSON object.
Rules:
1. Output ONLY raw JSON. No markdown, no backticks.
2. Keys: "title" (2-6 words naming the event), "summary" (100-130 words, neutral tone, plain text).
3. Use ONLY facts from the text."""

def parse_json(txt):
    if not isinstance(txt, str): return None
    a, b = txt.find("{"), txt.rfind("}")
    if a == -1 or b <= a: return None
    try: return json.loads(txt[a:b + 1])
    except: return None

def ai_summarize(j, labels):
    if not GROQ_KEY or _groq["disabled"]: return None
    prompt = f"ALREADY POSTED:\n" + ("\n".join(f"- {x}" for x in labels) if labels else "- (nothing yet)") + f"\n\nSOURCE: {j['source']}\nARTICLE:\n{j['text'][:3500]}"
    
    for attempt in range(3):
        model = GROQ_MODELS[_groq["idx"]]
        body = {"model": model, "temperature": 0.2, "max_completion_tokens": 1500, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]}
        try: 
            r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_KEY}"}, json=body, timeout=60)
        except Exception as e: 
            log(f"Groq request error: {e}")
            time.sleep(2)
            continue
        
        if r.status_code == 429:
            log("Groq rate limit hit, waiting...")
            time.sleep(5)
            continue
        if r.status_code == 404:
            _groq["idx"] += 1
            if _groq["idx"] >= len(GROQ_MODELS): _groq["disabled"] = True; return None
            continue
        if r.ok:
            try: return parse_json(r.json()["choices"][0]["message"]["content"])
            except: return None
    return None

def build_caption(label, url, summary):
    label = clip(label, 70)
    body = clip(summary, 1000 - len(label) - 12)
    return f'<a href="{htmllib.escape(url, quote=True)}"><b>{htmllib.escape(label)}</b></a>\n\n<blockquote>{htmllib.escape(body)}</blockquote>'

def tg(method, **kw):
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/{method}", data={k: v for k, v in kw.items() if not isinstance(v, (dict, list)) and v is not None}, files=kw.get("files"), timeout=30)
    if not r.ok:
        log(f"TG Error {r.status_code}: {r.text[:100]}")
    return r.ok

def publish(j, label, summary):
    if DRY_RUN: return True
    caption = build_caption(label, j["url"], summary)
    if j.get("image_bytes") and tg("sendPhoto", files={"photo": ("cover.jpg", j["image_bytes"])}, caption=caption, parse_mode="HTML"): return True
    if j.get("image") and tg("sendPhoto", photo=j["image"], caption=caption, parse_mode="HTML"): return True
    return tg("sendMessage", text=caption, parse_mode="HTML", link_preview_options={"is_disabled": True})

# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    if not DRY_RUN and not (TG_TOKEN and TG_CHAT): 
        log("Missing TG Tokens."); return 1
    if not GROQ_KEY: 
        log("Missing Groq Key."); return 1

    try:
        with open(STATE_PATH, encoding="utf-8") as f: st = json.load(f); st.setdefault("items", {})
    except: st = {"items": {}}
    
    cutoff = time.time() - 21 * 86400
    st["items"] = {k: v for k, v in st["items"].items() if v.get("ts", 0) >= cutoff}

    items = gather()
    seen_now, fresh = set(), []
    for j in items:
        k = ukey(j["url"])
        if k not in st["items"] and k not in seen_now:
            seen_now.add(k); fresh.append(j)
    
    log(f"{len(items)} stories found, {len(fresh)} fresh.")
    if not fresh: return 0

    candidates = rank(fresh)[: MAX_EVAL]
    log(f"Downloading text & images for {len(candidates)} items...")
    with ThreadPoolExecutor(max_workers=15) as pool:
        candidates = list(pool.map(enrich_and_download_image, candidates))

    labels = [v.get("label") for v in st["items"].values() if v.get("status") == "posted" and v.get("label")]
    labels = list(reversed(labels[-50:]))
    posted = 0

    for j in candidates:
        if posted >= MAX_POSTS: break
            
        log(f"Evaluating: {j['title'][:50]}...")
        res = ai_summarize(j, labels)
        
        if GROQ_KEY and not _groq["disabled"]: time.sleep(1.2) 
        
        # --- THE FIREHOSE FALLBACK ---
        # If AI fails, we STILL POST using the raw data!
        if not isinstance(res, dict):
            log(" -> AI failed. Falling back to raw RSS data.")
            label = j['title'][:70]
            summary = j['excerpt'][:800] if j.get('excerpt') else "Read the full article at the link."
        else:
            label = re.sub(r"\s+", " ", str(res.get("title") or "")).strip().strip(".:;-")
            summary = re.sub(r"[*_`#]+", "", re.sub(r"\s+", " ", str(res.get("summary") or ""))).strip()

        # Ensure no empty posts
        if not label: label = j['title'][:70]
        if len(summary) < 20: summary = j.get('excerpt', 'No summary available.')[:800]
            
        log(f" -> Attempting to post: {label}...")
        if publish(j, label, summary):
            st["items"][ukey(j["url"])] = {"ts": int(time.time()), "status": "posted", "label": label, "title": j["title"][:140]}
            labels.insert(0, label)
            posted += 1
            log(f" -> SUCCESS: Posted {label}")
            
            if posted % 5 == 0:
                with open(STATE_PATH, "w", encoding="utf-8") as f: json.dump(st, f, indent=1, ensure_ascii=False)
            
            time.sleep(2.5) 
        else:
            log(f" -> FAILED: Could not publish to Telegram.")

    with open(STATE_PATH, "w", encoding="utf-8") as f: json.dump(st, f, indent=1, ensure_ascii=False)
    log(f"Done: {posted} posted.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

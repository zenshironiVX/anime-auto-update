"""
scraper_anime.py — ULTRA Edition v2 (Debug + Robust)
แก้ไข:
  1. HTTP status log ทุก request (--debug)
  2. SSL context ถูกต้อง
  3. selector fallback หลายแบบ
  4. dump HTML หน้าแรก (--debug)
  5. warmup cookie ก่อนเริ่ม
"""
import json, os, argparse, asyncio, aiohttp, time, base64, re, ssl
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

CONCURRENT_REQUESTS = 80
TIMEOUT_SECS        = 20
MAX_RETRIES         = 3
CONNECTOR_LIMIT     = 120
BASE_URL            = "https://anime-hdzero.com"
DEBUG_MODE          = False

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# ── HTTP ──────────────────────────────────────────────
async def fetch(session, sem, url):
    async with sem:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECS),
                    allow_redirects=True) as resp:

                    if DEBUG_MODE:
                        print(f"  [DEBUG] HTTP {resp.status} {url[:90]}")

                    if resp.status == 200:
                        return await resp.text(errors="replace")
                    elif resp.status == 403:
                        body = await resp.text(errors="replace")
                        print(f"  [!] 403 Forbidden: {url[:70]}")
                        if DEBUG_MODE: print(f"       body={body[:300]}")
                        await asyncio.sleep(2**attempt); continue
                    elif resp.status == 429:
                        wait = 5*attempt
                        print(f"  [!] 429 Rate-limit — รอ {wait}s")
                        await asyncio.sleep(wait); continue
                    elif resp.status >= 500:
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(2**attempt); continue
                        print(f"  [!] {resp.status} Server error: {url[:70]}")
                        return None
                    else:
                        print(f"  [!] HTTP {resp.status}: {url[:70]}")
                        return None
            except asyncio.TimeoutError:
                print(f"  [!] Timeout (attempt {attempt}): {url[:70]}")
                if attempt < MAX_RETRIES: await asyncio.sleep(attempt*2)
            except aiohttp.ClientConnectorError as e:
                print(f"  [!] Connect error: {e}"); return None
            except Exception as e:
                if attempt == MAX_RETRIES:
                    print(f"  [!] {type(e).__name__}: {e}"); return None
                await asyncio.sleep(attempt)
    return None

# ── URL builder ───────────────────────────────────────
def build_list_url(source_id, page):
    if source_id == "HOME":
        return f"{BASE_URL}/?page={page}"
    return f"{BASE_URL}/category/{source_id}?page={page}"

def make_abs(href):
    if href.startswith("http"): return href
    return BASE_URL + href if href.startswith("/") else f"{BASE_URL}/{href}"

# ── Parsers ───────────────────────────────────────────
def parse_anime_list(html, label=""):
    soup = BeautifulSoup(html, "html.parser")
    # try selectors in order
    cards = soup.select("a.group.block")
    if not cards:
        cards = [a for a in soup.find_all("a", href=True)
                 if re.search(r"/anime/\d+", a.get("href",""))]
    if DEBUG_MODE:
        print(f"  [DEBUG][{label}] cards found: {len(cards)}")
        if not cards:
            print(f"  [DEBUG] HTML snippet: {html[:600]}")
    out = []
    for card in cards:
        href = card.get("href","")
        if not re.search(r"/anime/\d+", href): continue
        img = card.find("img")
        title = (img.get("alt","") if img else "").strip()
        if not title:
            fd = card.find(class_=lambda c: c and "font-display" in c)
            title = fd.get_text(strip=True) if fd else card.get_text(strip=True)[:80]
        cover = ""
        if img:
            cover = img.get("src","") or ""
            if not cover:
                ss = img.get("srcset","")
                if ss: cover = ss.split(",")[0].strip().split()[0]
        sticker = card.find(class_="sticker")
        badge = sticker.get_text(strip=True) if sticker else ""
        out.append({"title":title,"link":make_abs(href),"cover":cover,
                    "badge":badge,"episodes":[],"source_cat_id":"","sort_order":0})
    return out

def detect_cat(title, badge):
    if badge=="MOVIE" or "เดอะมูฟวี่" in title: return "3"
    if "พากย์ไทย" in title or badge=="DUB": return "2"
    return "1"

def parse_episodes(html):
    soup = BeautifulSoup(html, "html.parser")
    eps = []
    for a in soup.select("a.ep-row"):
        href = a.get("href","")
        if "/episode/" not in href: continue
        span = a.find("span")
        title = span.get_text(strip=True) if span else href.split("/")[-1]
        eps.append({"title":title,"url":make_abs(href)})
    if not eps:
        for a in soup.find_all("a", href=re.compile(r"/episode/")):
            eps.append({"title":a.get_text(strip=True) or a["href"].split("/")[-1],
                        "url":make_abs(a["href"])})
    eps.sort(key=lambda e: int(m.group(1)) if (m:=re.search(r"/episode/(\d+)",e["url"])) else 0)
    return eps

def decode_video(html):
    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.find("iframe", src=re.compile(r"embed\.php"))
    if not iframe: iframe = soup.find("iframe")
    if not iframe: return None
    src = iframe.get("src","")
    if not src: return None
    qs = parse_qs(urlparse(src).query)
    if "link" in qs:
        b64 = qs["link"][0] + "=" * ((4-len(qs["link"][0])%4)%4)
        try:
            real = base64.b64decode(b64).decode("utf-8")
            if real.startswith("http"): return real
        except: pass
    return src if src.startswith("http") else make_abs(src)

# ── Crawlers ──────────────────────────────────────────
async def crawl_page(session, sem, source_id, page):
    url = build_list_url(source_id, page)
    html = await fetch(session, sem, url)
    if not html: return []
    if DEBUG_MODE and page == 1:
        fname = f"debug_{source_id}_p1.html"
        open(fname,"w",encoding="utf-8").write(html)
        print(f"  [DEBUG] dump → {fname} ({len(html):,} bytes)")
    animes = parse_anime_list(html, label=f"{source_id}/p{page}")
    for a in animes:
        a["source_cat_id"] = detect_cat(a["title"],a["badge"]) if source_id=="HOME" else source_id
    return animes

async def crawl_eps(session, sem, anime):
    html = await fetch(session, sem, anime["link"])
    if html: anime["episodes"] = parse_episodes(html)

async def crawl_vid(session, sem, ep):
    html = await fetch(session, sem, ep["url"])
    if html:
        real = decode_video(html)
        if real: ep["url"] = real

# ── Cache ─────────────────────────────────────────────
def load_cache(path="anime_data.js"):
    cache = {}
    try:
        text = open(path, encoding="utf-8").read().strip()
        text = re.sub(r"^\s*const\s+animeData\s*=\s*","",text)
        text = re.sub(r";\s*$","",text)
        old = json.loads(text)
        for cd in old.values():
            for a in cd.get("animes",[]):
                link = a.get("link","")
                em = {ep["title"]:ep["url"] for ep in a.get("episodes",[])
                      if ep.get("title") and ep.get("url") and "/episode/" not in ep["url"]}
                if link: cache[link] = em
        print(f"📦 โหลดแคช: {len(cache)} เรื่อง")
    except FileNotFoundError:
        print("ℹ️  ไม่พบแคช — เริ่มใหม่")
    except Exception as e:
        print(f"⚠️  แคชผิดพลาด ({e}) — เริ่มใหม่")
    return cache

# ── Main pipeline ─────────────────────────────────────
async def run_all(categories, is_test, use_cache):
    cache = load_cache() if use_cache else {}
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)
    conn = aiohttp.TCPConnector(limit=CONNECTOR_LIMIT, ssl=ssl_ctx, ttl_dns_cache=300)

    async with aiohttp.ClientSession(headers=HEADERS, connector=conn,
                                     cookie_jar=aiohttp.CookieJar()) as session:
        # warmup
        print("🔄 Warmup...")
        await fetch(session, sem, BASE_URL)
        await asyncio.sleep(0.5)

        # 1) scan pages
        all_animes, seen, sort_idx = [], set(), 1_000_000
        for cat in categories:
            print(f"\n[1/3] {cat['name']}")
            max_pg = 1 if is_test else cat["max_page"]
            empty_streak = 0
            for page in range(1, max_pg+1):
                batch = await crawl_page(session, sem, cat["source_id"], page)
                if not batch:
                    empty_streak += 1
                    print(f"  [!] หน้า {page} ว่าง (empty_streak={empty_streak})")
                    if empty_streak >= 2: break
                    await asyncio.sleep(1); continue
                empty_streak = 0
                added = 0
                for a in batch:
                    if a["link"] not in seen:
                        seen.add(a["link"])
                        a["sort_order"] = sort_idx; sort_idx -= 1
                        all_animes.append(a); added += 1
                print(f"  [+] หน้า {page}: +{added} (รวม {len(all_animes)})")
                if is_test: break

        print(f"\n📌 รวม {len(all_animes)} เรื่อง")
        if not all_animes:
            print("\n❌ ได้ 0 เรื่อง! ลองรัน: python scraper_anime.py --debug --test")
            print("   แล้วดูไฟล์ debug_HOME_p1.html ว่า HTML จริงมีอะไร")
            return []

        # 2) episodes
        print(f"\n[2/3] ดึงตอน...")
        tasks = [crawl_eps(session, sem, a) for a in all_animes]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro; done += 1
            if done % 50 == 0 or done == len(tasks):
                print(f"  [+] {done}/{len(tasks)}")

        # 2.5) check cache
        to_crack, cached_n = [], 0
        for a in all_animes:
            ac = cache.get(a["link"], {})
            for ep in a["episodes"]:
                if ep["title"] in ac:
                    ep["url"] = ac[ep["title"]]; cached_n += 1
                else:
                    to_crack.append(ep)
        total_eps = sum(len(a["episodes"]) for a in all_animes)
        print(f"\n📊 {total_eps} ตอน | แคช {cached_n} | ใหม่ {len(to_crack)}")

        # 3) video URLs
        if to_crack:
            print(f"\n[3/3] เจาะวิดีโอ {len(to_crack)} ตอน...")
            vtasks = [crawl_vid(session, sem, ep) for ep in to_crack]
            done = 0
            for coro in asyncio.as_completed(vtasks):
                await coro; done += 1
                if done % 200 == 0 or done == len(vtasks):
                    print(f"  [+] {done}/{len(vtasks)}")
        else:
            print("\n✨ ทุกตอนอยู่ในแคช")

    return all_animes

# ── Save ──────────────────────────────────────────────
def save_to_file(animes, path="anime_data.js"):
    cat_names = {"1":"ซับไทย","2":"พากย์ไทย","3":"เดอะมูฟวี่"}
    export = {}
    for a in animes:
        sid = a.get("source_cat_id","1")
        if sid not in cat_names: sid = "1"
        if sid not in export: export[sid] = {"name":cat_names[sid],"animes":[]}
        export[sid]["animes"].append({"title":a["title"],"link":a["link"],"cover":a["cover"],
            "badge":a.get("badge",""),"sort_order":a.get("sort_order",0),"episodes":a["episodes"]})
    for sid in export:
        export[sid]["animes"].sort(key=lambda x:x["sort_order"],reverse=True)
    try:
        with open(path,"w",encoding="utf-8") as f:
            f.write("const animeData = ")
            json.dump(export,f,ensure_ascii=False,indent=2)
            f.write(";")
        total = sum(len(v["animes"]) for v in export.values())
        eps = sum(len(a["episodes"]) for v in export.values() for a in v["animes"])
        print(f"\n✅ บันทึก '{path}': {total} เรื่อง {eps} ตอน")
    except Exception as e:
        print(f"❌ บันทึกผิดพลาด: {e}")
    return export

# ── API push ──────────────────────────────────────────
async def push_to_api(export_data):
    url = os.getenv("ADMIN_URL",""); key = os.getenv("SECRET_KEY","")
    if not url or not key: print("\n❌ ไม่พบ ADMIN_URL/SECRET_KEY"); return
    if "ajax_import=1" not in url:
        sep = "&" if "?" in url else "?"
        url = url.rstrip("/")+sep+"page=admin&ajax_import=1"
    BATCH=50; batches=[]
    for cid,cd in export_data.items():
        animes=cd["animes"]
        for i in range(0,len(animes),BATCH):
            batches.append({cid:{"name":cd["name"],"animes":animes[i:i+BATCH]}})
    h={"Content-Type":"application/json","X-Admin-Key":key}
    async with aiohttp.ClientSession(headers=h) as session:
        print(f"\n🚀 ส่ง {len(batches)} ชุด → {url}")
        for i,batch in enumerate(batches,1):
            try:
                async with session.post(url,json=batch,timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    text=await resp.text()
                    try:
                        r=json.loads(text)
                        print(f"  {'✅' if r.get('success') else '❌'} {i}/{len(batches)}: {r.get('message','')}")
                    except:
                        print(f"  [!] {i}/{len(batches)}: HTTP {resp.status} {text[:200]}")
            except Exception as e:
                print(f"  [!] {i}: {e}")
    print("✅ ส่งเสร็จ!")

# ── Entry point ───────────────────────────────────────
CATEGORIES = [
    {"source_id":"HOME","name":"หน้าหลัก","max_page":268},
    {"source_id":"2","name":"พากย์ไทย","max_page":98},
    {"source_id":"1","name":"ซับไทย","max_page":127},
    {"source_id":"3","name":"เดอะมูฟวี่","max_page":44},
]

def main():
    global DEBUG_MODE
    p = argparse.ArgumentParser()
    p.add_argument("--auto",      action="store_true")
    p.add_argument("--full",      action="store_true")
    p.add_argument("--test",      action="store_true")
    p.add_argument("--debug",     action="store_true", help="แสดง HTTP status + dump HTML")
    p.add_argument("--no-upload", action="store_true")
    args = p.parse_args()
    DEBUG_MODE = args.debug
    if DEBUG_MODE: print("🔍 DEBUG MODE ON\n")
    print("🚀 Anime Scraper — ⚡ ULTRA v2\n")
    if args.auto:   is_test,use_cache,do_upload = False,True,not args.no_upload; print("🤖 AUTO")
    elif args.test: is_test,use_cache,do_upload = True,False,False;              print("🧪 TEST")
    elif args.full: is_test,use_cache,do_upload = False,False,not args.no_upload;print("💥 FULL")
    else:
        print("1=Full  2=Test  3=Fast Update")
        c=input("👉 ").strip()
        is_test,use_cache,do_upload = c=="2",c=="3",False
    t0=time.time()
    animes = asyncio.run(run_all(CATEGORIES,is_test,use_cache))
    export = save_to_file(animes)
    if do_upload: asyncio.run(push_to_api(export))
    print(f"\n⏱  {time.time()-t0:.1f}s")
    if not any([args.auto,args.full,args.test,args.debug]): input("\nEnter เพื่อปิด...")

if __name__ == "__main__":
    main()

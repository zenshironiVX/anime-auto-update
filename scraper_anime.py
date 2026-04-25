"""
scraper_anime.py — ULTRA Edition v5 (Ultimate Ad Bypass + Anti-Bot Spoofing)
แก้ไข:
  1. ปลอมแปลง Headers เต็มรูปแบบเพื่อหลบหลีก Cloudflare / Bot Protection
  2. เพิ่มระบบตรวจจับแจ้งเตือนหากโดน Cloudflare บล็อก (ป้องกันปัญหาดึงมาได้ 0 เรื่อง)
  3. Aggressive Fallback กวาดทุกลิงก์ /anime/ แบบครอบจักรวาล
  4. ถอดรหัส Base64 ของ iframe ขั้นเทพ (แก้อาการ Padding error)
"""
import json, os, argparse, asyncio, aiohttp, time, base64, re, ssl, urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

CONCURRENT_REQUESTS = 80
TIMEOUT_SECS        = 20
MAX_RETRIES         = 3
CONNECTOR_LIMIT     = 120
BASE_URL            = "https://anime-hdzero.com"
DEBUG_MODE          = False

# ปลอมตัวเป็นเบราว์เซอร์จริง 100% เพื่อลดโอกาสโดนแบน
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Sec-Ch-Ua": "\"Chromium\";v=\"124\", \"Google Chrome\";v=\"124\", \"Not-A.Brand\";v=\"99\"",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "\"Windows\"",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
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
                    elif resp.status in [403, 503]:
                        print(f"  [!] {resp.status} Forbidden/Service Unavailable: {url[:70]} (อาจติด Cloudflare)")
                        await asyncio.sleep(2**attempt); continue
                    elif resp.status == 429:
                        wait = 5*attempt
                        print(f"  [!] 429 Rate-limit — รอ {wait}s")
                        await asyncio.sleep(wait); continue
                    elif resp.status >= 500:
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(2**attempt); continue
                        return None
                    else:
                        if DEBUG_MODE: print(f"  [!] HTTP {resp.status}: {url[:70]}")
                        return None
            except asyncio.TimeoutError:
                if DEBUG_MODE: print(f"  [!] Timeout (attempt {attempt}): {url[:70]}")
                if attempt < MAX_RETRIES: await asyncio.sleep(attempt*2)
            except aiohttp.ClientConnectorError as e:
                if DEBUG_MODE: print(f"  [!] Connect error: {e}")
                return None
            except Exception as e:
                if attempt == MAX_RETRIES:
                    if DEBUG_MODE: print(f"  [!] {type(e).__name__}: {e}")
                    return None
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
    # ตรวจจับ Cloudflare
    if "Just a moment..." in html or "cf-browser-verification" in html or "ray_id" in html:
        print(f"  [!] 🚨 ตรวจพบระบบป้องกันบอท (Cloudflare) ในหน้า {label}!")
        return []

    soup = BeautifulSoup(html, "html.parser")
    
    # 1. พยายามหาจาก CSS Class ปัจจุบัน (a.group.block)
    cards = soup.select("a.group.block")
    
    # 2. Aggressive Fallback: กวาดทุกลิงก์ที่มี /anime/ ทั่วทั้งหน้า
    if not cards:
        cards = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"^/anime/\d+/?$", href) or re.search(r"^https?://[^/]+/anime/\d+/?$", href):
                cards.append(a)
    
    if DEBUG_MODE:
        print(f"  [DEBUG][{label}] พบการ์ดอนิเมะ: {len(cards)} ใบ")

    out = []
    seen_links = set()
    
    for card in cards:
        href = card.get("href", "")
        if not href or "/anime/" not in href or "/episode/" in href: 
            continue
            
        abs_link = make_abs(href)
        if abs_link in seen_links: 
            continue
        seen_links.add(abs_link)

        img = card.find("img")

        # Title Extraction
        title = ""
        title_elem = card.select_one(".font-display")
        if not title_elem:
            title_elem = card.find(class_=lambda c: c and "font-display" in c)
            
        if title_elem:
            title = title_elem.get_text(strip=True)
        elif img and img.get("alt"):
            title = img.get("alt", "").strip()
            
        if not title:
            title = card.get_text(strip=True)[:80]
        if not title:
            title = f"Anime_{href.split('/')[-1]}"

        # Cover Image Extraction
        cover = img.get("src", "") if img else ""
        if not cover and img:
            ss = img.get("srcset", "")
            if ss: cover = ss.split(",")[0].strip().split()[0]
        
        # Badge Extraction (SUB, DUB, MOVIE, AIRING)
        badge_elem = card.select_one(".sticker")
        if not badge_elem:
            badge_elem = card.find(class_="sticker")
        badge = badge_elem.get_text(strip=True) if badge_elem else ""

        out.append({
            "title": title,
            "link": abs_link,
            "cover": cover,
            "badge": badge,
            "episodes": [],
            "source_cat_id": "",
            "sort_order": 0
        })
    return out

def detect_cat(title, badge):
    if badge == "MOVIE" or "เดอะมูฟวี่" in title or "Movie" in badge: return "3"
    if "พากย์ไทย" in title or badge == "DUB": return "2"
    return "1"

def parse_episodes(html):
    soup = BeautifulSoup(html, "html.parser")
    eps = []
    
    # 1. ค้นหาจาก CSS Class
    for a in soup.select("a.ep-row"):
        href = a.get("href", "")
        if "/episode/" not in href: continue
        
        span = a.find("span")
        title = span.get_text(strip=True) if span else href.split("/")[-1]
        eps.append({"title": title, "url": make_abs(href)})
        
    # 2. Fallback
    if not eps:
        for a in soup.find_all("a", href=re.compile(r"/episode/\d+")):
            title = a.get_text(strip=True) or a.get("href", "").split("/")[-1]
            eps.append({"title": title, "url": make_abs(a["href"])})
    
    # Sort Episodes
    def extract_ep_num(ep):
        title = ep.get("title", "")
        url = ep.get("url", "")
        match = re.search(r'(?:ตอนที่|EP\.?)\s*(\d+)', title, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match_url = re.search(r'/episode/(\d+)', url)
        return int(match_url.group(1)) if match_url else 0

    eps.sort(key=extract_ep_num)
    return eps

def decode_video(html):
    """เจาะ iframe โฆษณา/เว็บพนัน เพื่อดึงลิ้งก์สตรีมจริง (akuma-player ฯลฯ)"""
    soup = BeautifulSoup(html, "html.parser")
    iframes = soup.find_all("iframe")
    
    for iframe in iframes:
        src = iframe.get("src", "")
        if not src: continue
        
        # 1. เช็คโครงสร้าง embed.php?link= (Base64 Encoded)
        if "embed.php" in src and "link=" in src:
            qs = parse_qs(urlparse(src).query)
            if "link" in qs:
                encoded_link = qs["link"][0]
                # แก้ URL Encoding
                encoded_link = urllib.parse.unquote(encoded_link)
                # เติม Padding ให้ครบถ้วน
                b64 = encoded_link + "=" * ((4 - len(encoded_link) % 4) % 4)
                try:
                    real_url = base64.b64decode(b64).decode("utf-8")
                    if real_url.startswith("http"):
                        return real_url
                except Exception as e:
                    if DEBUG_MODE: print(f"  [DEBUG] Base64 Decode Error: {e}")
                    pass
        
        # 2. ค้นหาเครื่องเล่นวิดีโอทั่วไป
        elif any(player in src for player in ["akuma-player", "dood", "ok.ru", "stream"]):
            return src if src.startswith("http") else make_abs(src)

    return None

# ── Crawlers ──────────────────────────────────────────
async def crawl_page(session, sem, source_id, page):
    url = build_list_url(source_id, page)
    html = await fetch(session, sem, url)
    if not html: return []
    
    # ดัมพ์ไฟล์ HTML ออกมาเช็คในโหมด Debug
    if DEBUG_MODE and page == 1:
        fname = f"debug_{source_id}_p1.html"
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  [DEBUG] บันทึก HTML หน้าแรกไปที่ {fname} ({len(html):,} bytes)")
        except:
            pass
            
    animes = parse_anime_list(html, label=f"{source_id}/p{page}")
    for a in animes:
        a["source_cat_id"] = detect_cat(a["title"], a["badge"]) if source_id=="HOME" else source_id
    return animes

async def crawl_eps(session, sem, anime):
    html = await fetch(session, sem, anime["link"])
    if html: 
        anime["episodes"] = parse_episodes(html)

async def crawl_vid(session, sem, ep):
    html = await fetch(session, sem, ep["url"])
    if html:
        real_url = decode_video(html)
        if real_url: 
            ep["url"] = real_url

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
            print(f"\n[1/3] หมวดหมู่: {cat['name']}")
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
                print(f"  [+] ดึงหน้า {page}: สำเร็จ +{added} เรื่อง (รวม {len(all_animes)})")
                if is_test: break

        print(f"\n📌 ดึงข้อมูลโครงสร้างเสร็จสิ้น: รวม {len(all_animes)} เรื่อง")
        if not all_animes:
            print("\n❌ ได้ 0 เรื่อง!")
            print("💡 คำแนะนำ: หากคุณเจอ 0 เรื่องตลอด อาจเป็นไปได้สูงมากที่เว็บไซต์บล็อก IP หรือป้องกันบอท (Cloudflare) ลองรัน:")
            print("   python scraper_anime.py --debug --test")
            print("   และเข้าไปเปิดดูไฟล์ debug_HOME_p1.html เพื่อตรวจสอบ")
            return []

        # 2) episodes
        print(f"\n[2/3] กำลังสแกนหาลิสต์ตอนทั้งหมด...")
        tasks = [crawl_eps(session, sem, a) for a in all_animes]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro; done += 1
            if done % 50 == 0 or done == len(tasks):
                print(f"  [+] สแกนตอนแล้ว: {done}/{len(tasks)} เรื่อง")

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
        print(f"\n📊 พบทั้งหมด {total_eps} ตอน | ใช้แคชเก่า {cached_n} ตอน | ต้องเจาะลิ้งก์ใหม่ {len(to_crack)} ตอน")

        # 3) video URLs
        if to_crack:
            print(f"\n[3/3] กำลังเจาะทะลวงดึงลิ้งก์วิดีโอจริง (Bypass Ads) {len(to_crack)} ตอน...")
            vtasks = [crawl_vid(session, sem, ep) for ep in to_crack]
            done = 0
            for coro in asyncio.as_completed(vtasks):
                await coro; done += 1
                if done % 200 == 0 or done == len(vtasks):
                    print(f"  [+] เจาะเสร็จแล้ว: {done}/{len(vtasks)} ตอน")
        else:
            print("\n✨ ทุกตอนมีลิ้งก์จริงในแคชแล้ว ข้ามการเจาะลิ้งก์")

    return all_animes

# ── Save ──────────────────────────────────────────────
def save_to_file(animes, path="anime_data.js"):
    cat_names = {"1":"ซับไทย", "2":"พากย์ไทย", "3":"เดอะมูฟวี่"}
    export = {}
    for a in animes:
        sid = a.get("source_cat_id","1")
        if sid not in cat_names: sid = "1"
        if sid not in export: export[sid] = {"name":cat_names[sid], "animes":[]}
        export[sid]["animes"].append({
            "title": a["title"],
            "link": a["link"],
            "cover": a["cover"],
            "badge": a.get("badge",""),
            "sort_order": a.get("sort_order",0),
            "episodes": a["episodes"]
        })
    for sid in export:
        export[sid]["animes"].sort(key=lambda x:x["sort_order"], reverse=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("const animeData = ")
            json.dump(export, f, ensure_ascii=False, indent=2)
            f.write(";")
        total = sum(len(v["animes"]) for v in export.values())
        eps = sum(len(a["episodes"]) for v in export.values() for a in v["animes"])
        print(f"\n✅ บันทึกไฟล์ '{path}' สำเร็จ! ({total} เรื่อง {eps} ตอน)")
    except Exception as e:
        print(f"❌ บันทึกผิดพลาด: {e}")
    return export

# ── API push ──────────────────────────────────────────
async def push_to_api(export_data):
    url = os.getenv("ADMIN_URL","")
    key = os.getenv("SECRET_KEY","")
    if not url or not key: 
        print("\nℹ️ ไม่พบ ADMIN_URL หรือ SECRET_KEY ข้ามการอัปโหลดเข้าเซิร์ฟเวอร์")
        return
        
    if "ajax_import=1" not in url:
        sep = "&" if "?" in url else "?"
        url = url.rstrip("/") + sep + "page=admin&ajax_import=1"
        
    BATCH = 50
    batches = []
    for cid, cd in export_data.items():
        animes = cd["animes"]
        for i in range(0, len(animes), BATCH):
            batches.append({cid: {"name": cd["name"], "animes": animes[i:i+BATCH]}})
            
    h = {"Content-Type":"application/json", "X-Admin-Key":key}
    async with aiohttp.ClientSession(headers=h) as session:
        print(f"\n🚀 กำลังส่ง {len(batches)} ชุดข้อมูล → API: {url}")
        for i, batch in enumerate(batches, 1):
            try:
                async with session.post(url, json=batch, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    text = await resp.text()
                    try:
                        r = json.loads(text)
                        print(f"  {'✅' if r.get('success') else '❌'} ชุดที่ {i}/{len(batches)}: {r.get('message','')}")
                    except:
                        print(f"  [!] ชุดที่ {i}/{len(batches)}: HTTP {resp.status} {text[:100]}...")
            except Exception as e:
                print(f"  [!] ชุดที่ {i}: ส่งผิดพลาด ({e})")
    print("✅ การอัปโหลดเสร็จสิ้น!")

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
    p.add_argument("--debug",     action="store_true", help="แสดง HTTP status และบันทึกไฟล์ HTML ตรวจสอบ")
    p.add_argument("--no-upload", action="store_true")
    args = p.parse_args()
    
    DEBUG_MODE = args.debug
    if DEBUG_MODE: print("🔍 โหมด DEBUG: เปิดใช้งาน\n")
    
    print("🚀 Anime Scraper — ⚡ ULTRA v5 (Ultimate Ad Bypass + Anti-Bot Spoofing)\n")
    
    if args.auto:   
        is_test, use_cache, do_upload = False, True, not args.no_upload
        print("🤖 หมวด: AUTO (อัปเดตเฉพาะตอนใหม่)")
    elif args.test: 
        is_test, use_cache, do_upload = True, False, False
        print("🧪 หมวด: TEST (ดึงเฉพาะหน้าแรกเพื่อทดสอบ)")
    elif args.full: 
        is_test, use_cache, do_upload = False, False, not args.no_upload
        print("💥 หมวด: FULL (ดึงใหม่ทั้งหมด ล้างแคช)")
    else:
        print("กรุณาเลือกโหมดการทำงาน:")
        print("  1 = ดึงใหม่ทั้งหมด (Full)")
        print("  2 = ทดสอบระบบ (Test 1 หน้า)")
        print("  3 = อัปเดตแบบรวดเร็ว (Fast Update / ใช้ Cache)")
        c = input("👉 เลือกตัวเลข: ").strip()
        is_test, use_cache, do_upload = (c=="2"), (c=="3"), False
        
    t0 = time.time()
    
    # Run Async loop
    animes = asyncio.run(run_all(CATEGORIES, is_test, use_cache))
    export = save_to_file(animes)
    
    if do_upload: 
        asyncio.run(push_to_api(export))
        
    print(f"\n⏱  ใช้เวลาทั้งหมด: {time.time()-t0:.1f} วินาที")
    if not any([args.auto, args.full, args.test]): 
        input("\nกด Enter เพื่อปิดโปรแกรม...")

if __name__ == "__main__":
    main()

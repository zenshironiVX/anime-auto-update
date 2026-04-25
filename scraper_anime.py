"""
scraper_anime.py — ULTRA Edition v16 (GitHub Actions / Auto 3-Pages Limit)
แก้ไข:
  1. โหมด --auto จะจำกัดการสแกนแค่ 3 หน้าแรกของแต่ละหมวดหมู่ เพื่อความรวดเร็วในการอัปเดตและป้องกันการถูกแบน
  2. เพิ่ม Arguments '--no-sandbox' และ '--disable-dev-shm-usage' เพื่อให้รันบน Linux/GitHub Actions ได้
  3. เปิดใช้งาน Headless เต็มรูปแบบ
"""
import json, os, argparse, asyncio, time, base64, re, urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import aiohttp
from playwright.async_api import async_playwright

CONCURRENT_REQUESTS = 8  # ลดเพื่อไม่ให้กิน RAM ของ GitHub Actions มากเกินไป
TIMEOUT_SECS        = 30
MAX_RETRIES         = 3
BASE_URL            = "https://anime-hdzero.com"
DEBUG_MODE          = False

# ── HTTP (Powered by Playwright Visual Tabs) ───────────────────────
async def fetch(context, sem, url):
    async with sem:
        for attempt in range(1, MAX_RETRIES + 1):
            page = None
            try:
                page = await context.new_page()
                if DEBUG_MODE:
                    print(f"  [DEBUG] เปิดแท็บโหลด: {url[:90]}")
                    
                await page.goto(url, timeout=TIMEOUT_SECS * 1000, wait_until="domcontentloaded")

                title = await page.title()
                if "Just a moment" in title or "Cloudflare" in title or "Attention Required" in title:
                    if DEBUG_MODE:
                        print(f"  [!] รอแก้ Cloudflare แท็บย่อย: {url[:50]}")
                    try:
                        await page.wait_for_function("document.title.indexOf('Just a moment') === -1", timeout=15000)
                    except:
                        pass

                html = await page.content()
                await page.close()
                return html

            except Exception as e:
                if page:
                    try: await page.close()
                    except: pass
                    
                err_msg = str(e).lower()
                if "timeout" in err_msg:
                    if DEBUG_MODE: print(f"  [!] Timeout (attempt {attempt}): {url[:70]}")
                else:
                    if DEBUG_MODE and attempt == MAX_RETRIES: print(f"  [!] {type(e).__name__}: {e}")
                
                if attempt < MAX_RETRIES: 
                    await asyncio.sleep(attempt * 2)
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
    cards = soup.select("a.group.block")
    
    if not cards:
        cards = soup.find_all("a", href=re.compile(r"/anime/\d+"))
        
    if not cards:
        if DEBUG_MODE:
            page_title = soup.title.string.strip() if soup.title else "No Title"
            print(f"  [DEBUG] ข้อมูลว่างเปล่า! ชื่อเพจ: '{page_title}'")
        return []
    
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

        cover = img.get("src", "") if img else ""
        if not cover and img:
            ss = img.get("srcset", "")
            if ss: cover = ss.split(",")[0].strip().split()[0]
        
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
    
    for a in soup.select("a.ep-row"):
        href = a.get("href", "")
        if "/episode/" not in href: continue
        span = a.find("span")
        title = span.get_text(strip=True) if span else href.split("/")[-1]
        eps.append({"title": title, "url": make_abs(href)})
        
    if not eps:
        for a in soup.find_all("a", href=re.compile(r"/episode/\d+")):
            title = a.get_text(strip=True) or a.get("href", "").split("/")[-1]
            eps.append({"title": title, "url": make_abs(a["href"])})
    
    def extract_ep_num(ep):
        title = ep.get("title", "")
        url = ep.get("url", "")
        match = re.search(r'(?:ตอนที่|EP\.?)\s*(\d+)', title, re.IGNORECASE)
        if match: return int(match.group(1))
        match_url = re.search(r'/episode/(\d+)', url)
        return int(match_url.group(1)) if match_url else 0

    eps.sort(key=extract_ep_num)
    return eps

def decode_video(html):
    soup = BeautifulSoup(html, "html.parser")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if not src: continue
        
        if "embed.php" in src and "link=" in src:
            qs = parse_qs(urlparse(src).query)
            if "link" in qs:
                encoded_link = urllib.parse.unquote(qs["link"][0])
                b64 = encoded_link + "=" * ((4 - len(encoded_link) % 4) % 4)
                try:
                    real_url = base64.b64decode(b64).decode("utf-8")
                    if real_url.startswith("http"): return real_url
                except:
                    pass
        elif any(player in src for player in ["akuma-player", "dood", "ok.ru", "stream"]):
            return src if src.startswith("http") else make_abs(src)
    return None

# ── Crawlers ──────────────────────────────────────────
async def crawl_page(context, sem, source_id, page):
    url = build_list_url(source_id, page)
    html = await fetch(context, sem, url)
    if not html: return []
            
    animes = parse_anime_list(html, label=f"{source_id}/p{page}")
    for a in animes:
        a["source_cat_id"] = detect_cat(a["title"], a["badge"]) if source_id=="HOME" else source_id
    return animes

async def crawl_eps(context, sem, anime):
    html = await fetch(context, sem, anime["link"])
    if html: anime["episodes"] = parse_episodes(html)

async def crawl_vid(context, sem, ep):
    html = await fetch(context, sem, ep["url"])
    if html:
        real_url = decode_video(html)
        if real_url: ep["url"] = real_url

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
    except:
        print("ℹ️  ไม่พบแคช — เริ่มใหม่")
    return cache

# ── Main pipeline ─────────────────────────────────────
async def run_all(categories, is_test, use_cache, is_auto=False):
    cache = load_cache() if use_cache else {}
    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

    print("\n🌐 [ระบบทะลวง CF] กำลังเปิด Chrome (โหมดเบื้องหลัง)...")
    async with async_playwright() as p:
        # สิ่งสำคัญสำหรับรันบน GitHub Actions: ต้องใช้ args เหล่านี้เพื่อป้องกันแครช
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        browser_context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = await browser_context.new_page()

        print(f"⏳ กำลังวิ่งเข้าเว็บ {BASE_URL} ...")
        try:
            await page.goto(BASE_URL, timeout=60000)
        except Exception:
            pass

        print("🛡️ กำลังตรวจสอบการเชื่อมต่อเบื้องหลัง...")
        passed = False
        for i in range(15):
            await asyncio.sleep(4)
            try:
                title = await page.title()
                content = await page.content()
                if "Just a moment" not in title and "Cloudflare" not in title:
                    if "/anime/" in content or "หน้าหลัก" in content:
                        print("✅ ทะลุเข้าหน้าเว็บหลักสำเร็จแล้ว!")
                        
                        try:
                            theme_btn = page.locator('button[title="สลับธีม"]')
                            if await theme_btn.count() > 0:
                                await theme_btn.first.click()
                                await asyncio.sleep(2)
                            else:
                                pass
                        except Exception:
                            pass

                        passed = True
                        break
            except:
                pass
            print(f"⏳ ({i+1}/15) รอให้ผ่านหน้าโหลดเบื้องหลัง...")

        if not passed:
            print("⚠️ หมดเวลา 60 วินาที อาจจะยังไม่ผ่านนะ แต่จะลองดึงข้อมูลดู")

        print(f"\n🚀 เริ่มกวาดข้อมูลแบบ Multi-Tab (โหลดพร้อมกัน {CONCURRENT_REQUESTS} แท็บ)...")
        
        all_animes, seen, sort_idx = [], set(), 1_000_000
        for cat in categories:
            print(f"\n[1/3] หมวดหมู่: {cat['name']}")
            
            # 🎯 หัวใจสำคัญของการแก้ไข: จำกัดหน้าถ้าเป็นโหมด Auto หรือ Test
            if is_test:
                max_pg = 1
            elif is_auto:
                max_pg = min(3, cat["max_page"]) # ดึงแค่ 3 หน้าแรกเท่านั้น!
            else:
                max_pg = cat["max_page"]

            empty_streak = 0
            for page_num in range(1, max_pg+1):
                batch = await crawl_page(browser_context, sem, cat["source_id"], page_num)
                if not batch:
                    empty_streak += 1
                    print(f"  [!] หน้า {page_num} ว่าง (empty_streak={empty_streak})")
                    if empty_streak >= 2: break
                    await asyncio.sleep(1); continue
                empty_streak = 0
                added = 0
                for a in batch:
                    if a["link"] not in seen:
                        seen.add(a["link"])
                        a["sort_order"] = sort_idx; sort_idx -= 1
                        all_animes.append(a); added += 1
                print(f"  [+] ดึงหน้า {page_num}: สำเร็จ +{added} เรื่อง (รวม {len(all_animes)})")

        print(f"\n📌 ดึงข้อมูลโครงสร้างเสร็จสิ้น: รวม {len(all_animes)} เรื่อง")
        if not all_animes:
            print("\n❌ ได้ 0 เรื่อง! การตรวจสอบบอทอาจจะยังไม่ผ่าน หรือเว็บเปลี่ยนโครงสร้างกะทันหัน")
            await browser.close()
            return []

        print(f"\n[2/3] กำลังสแกนหาลิสต์ตอนทั้งหมด...")
        tasks = [crawl_eps(browser_context, sem, a) for a in all_animes]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro; done += 1
            if done % 50 == 0 or done == len(tasks):
                print(f"  [+] สแกนตอนแล้ว: {done}/{len(tasks)} เรื่อง")

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

        if to_crack:
            print(f"\n[3/3] กำลังเจาะทะลวงดึงลิ้งก์วิดีโอจริง (Bypass Ads) {len(to_crack)} ตอน...")
            vtasks = [crawl_vid(browser_context, sem, ep) for ep in to_crack]
            done = 0
            for coro in asyncio.as_completed(vtasks):
                await coro; done += 1
                if done % 200 == 0 or done == len(vtasks):
                    print(f"  [+] เจาะเสร็จแล้ว: {done}/{len(vtasks)} ตอน")
        else:
            print("\n✨ ทุกตอนมีลิ้งก์จริงในแคชแล้ว ข้ามการเจาะลิ้งก์")

        await browser.close()
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
    async with aiohttp.ClientSession() as session:
        print(f"\n🚀 กำลังส่ง {len(batches)} ชุดข้อมูล → API: {url}")
        for i, batch in enumerate(batches, 1):
            try:
                async with session.post(url, json=batch, headers=h, timeout=aiohttp.ClientTimeout(total=60)) as resp:
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
    
    print("🚀 Anime Scraper — ⚡ ULTRA v16 (GitHub Actions / Auto 3-Pages Limit)\n")
    
    if args.auto:   
        is_test, use_cache, do_upload, is_auto = False, True, not args.no_upload, True
        print("🤖 หมวด: AUTO (อัปเดตเฉพาะ 3 หน้าแรกของแต่ละหมวด)")
    elif args.test: 
        is_test, use_cache, do_upload, is_auto = True, False, False, False
        print("🧪 หมวด: TEST (ดึงเฉพาะหน้าแรกเพื่อทดสอบ)")
    elif args.full: 
        is_test, use_cache, do_upload, is_auto = False, False, not args.no_upload, False
        print("💥 หมวด: FULL (ดึงใหม่ทั้งหมด ล้างแคช)")
    else:
        print("กรุณาเลือกโหมดการทำงาน:")
        print("  1 = ดึงใหม่ทั้งหมด (Full)")
        print("  2 = ทดสอบระบบ (Test 1 หน้า)")
        print("  3 = อัปเดตแบบรวดเร็ว (Fast Update / ใช้ Cache / จำกัด 3 หน้า)")
        c = input("👉 เลือกตัวเลข: ").strip()
        is_test, use_cache, do_upload, is_auto = (c=="2"), (c=="3"), False, (c=="3")
        
    t0 = time.time()
    
    # รัน Event loop ของ asyncio
    animes = asyncio.run(run_all(CATEGORIES, is_test, use_cache, is_auto))
    export = save_to_file(animes)
    
    if do_upload: 
        asyncio.run(push_to_api(export))
        
    print(f"\n⏱  ใช้เวลาทั้งหมด: {time.time()-t0:.1f} วินาที")
    if not any([args.auto, args.full, args.test]): 
        input("\nกด Enter เพื่อปิดโปรแกรม...")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        main()
    except KeyboardInterrupt:
        pass

"""
scraper_anime.py — ⚡ ULTRA Edition
สถาปัตยกรรมใหม่ทั้งหมด:
  - ใช้ asyncio + aiohttp แทน requests + ThreadPool
  - ยิง HTTP พร้อมกันได้ 200+ requests โดยไม่สิ้นเปลือง thread
  - Semaphore คุมไม่ให้ flood เว็บจนโดนแบน
  - Flat task queue: episode ทุกตอนจากทุกอนิเมะถูก queue รวมกัน ไม่มี nested pool
  - Pipeline: ดึง episode list → แตก task → เจาะวิดีโอ ทำงานคู่ขนานกันทั้งหมด
"""

import json
import os
import sys
import argparse
import asyncio
import aiohttp
import time
import base64
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import re
from Crypto.Cipher import AES

# ==================== ⚙️ CONFIG ====================
CONCURRENT_REQUESTS = 150   # จำนวน HTTP requests พร้อมกันสูงสุด
TIMEOUT_SECS        = 12    # timeout ต่อ request
MAX_RETRIES         = 3
CONNECTOR_LIMIT     = 200   # TCP connection pool size

# For local development only (Remote MySQL is often blocked on hosting)
DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "",
    "database": "magaz_anime",
    "charset":  "utf8mb4"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (HTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}
# ====================================================

# ─────────────────────────────────────────────────────
#  HTTP layer  (async)
# ─────────────────────────────────────────────────────

async def fetch(session: aiohttp.ClientSession, sem: asyncio.Semaphore, url: str):
    """GET url พร้อม retry + semaphore คุม concurrency"""
    async with sem:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECS)) as resp:
                    if resp.status == 200:
                        return await resp.text(errors="replace")
                    if resp.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None
            except Exception:
                if attempt == MAX_RETRIES:
                    return None
                await asyncio.sleep(2 ** attempt)
    return None


# ─────────────────────────────────────────────────────
#  Parse helpers  (sync, CPU-only)
# ─────────────────────────────────────────────────────

def parse_anime_list(html: str, cat_id: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for item in soup.select(".zk_grid .zk_col"):
        link = item.get("href")
        if not link:
            continue
        title_div = item.select_one(".zk_title")
        img_tag   = item.select_one("img")
        out.append({
            "source_cat_id": cat_id,
            "title":  title_div.text.strip() if title_div else "ไม่มีชื่อ",
            "link":   link,
            "cover":  img_tag.get("src", "") if img_tag else "",
            "episodes": [],
        })
    return out


def parse_episode_links(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    eps = []
    for p in soup.select("p.text-center"):
        a = p.select_one("a")
        if a and "watch" in a.get("href", ""):
            eps.append({"title": a.text.strip(), "url": a["href"]})
    return eps


def decode_iframe_src(html: str):
    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.select_one("iframe.embed-responsive-item")
    if not iframe:
        return None
    src = iframe.get("src", "")
    if not src:
        return None
    if "link=" in src:
        qs = parse_qs(urlparse(src).query)
        if "link" in qs:
            b64 = qs["link"][0]
            b64 += "=" * ((4 - len(b64) % 4) % 4)
            try:
                return base64.b64decode(b64).decode("utf-8")
            except Exception:
                pass
    return src


# ─────────────────────────────────────────────────────
#  Async pipeline
# ─────────────────────────────────────────────────────

async def crawl_page(session, sem, source_id, page) -> list:
    if source_id == "HOME":
        url = f"https://anime-hdzero.com/index.php?page={page}"
    else:
        url = f"https://anime-hdzero.com/cat/{source_id}/&page={page}"
        
    html = await fetch(session, sem, url)
    return parse_anime_list(html, str(source_id)) if html else []


async def crawl_episodes(session, sem, anime: dict) -> None:
    """ดึง episode list ของอนิเมะ 1 เรื่อง"""
    html = await fetch(session, sem, anime["link"])
    if html:
        anime["episodes"] = parse_episode_links(html)


async def crawl_video(session, sem, ep: dict) -> None:
    """เจาะ iframe URL ของ 1 ตอน"""
    html = await fetch(session, sem, ep["url"])
    if html:
        real_url = decode_iframe_src(html)
        if real_url:
            ep["url"] = real_url


async def run_all(categories: list, is_test: bool, use_cache: bool = True) -> list:
    sem       = asyncio.Semaphore(CONCURRENT_REQUESTS)
    connector = aiohttp.TCPConnector(limit=CONNECTOR_LIMIT, ttl_dns_cache=300)

    # --- Load Cache: { anime_link: { ep_url: resolved_video_url } } ---
    cache_map = {}
    if use_cache:
        try:
            with open("anime_data.js", "r", encoding="utf-8") as f:
                c_text = f.read().replace("const animeData = ", "").strip()
                if c_text.endswith(";"): c_text = c_text[:-1]
                old_data = json.loads(c_text)
                for cid in old_data:
                    for a in old_data[cid].get("animes", []):
                        ep_cache = {}
                        for ep in a.get("episodes", []):
                            # ถ้า URL ไม่ใช่ลิ้งค์ 'watch' ของต้นทาง แสดงว่าเจาะแล้ว
                            if "watch" not in ep["url"]:
                                ep_cache[ep["title"]] = ep["url"]
                        cache_map[a["link"]] = ep_cache
            print(f"📦 โหลดข้อมูลแคชสำเร็จ! พบรายการเดิม {len(cache_map)} เรื่อง (จะสแกนละเอียดรายตอน)")
        except Exception:
            print("ℹ️ ไม่พบไฟล์แคชเดิม หรือไฟล์รูปแบบผิด (เริ่มสแกนใหม่)")
    else:
        print("💥 โหมด Full Scan: จะสแกนข้อมูลใหม่ทั้งหมดทุกตอน")

    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        all_animes = []
        current_sort_index = 100000 
        
        seen_links = set()

        for cat in categories:
            print(f"\n[1/3] กำลังสแกนหมวดหมู่: {cat['name']}...")
            limit = 1 if is_test else cat["max_page"]
            
            # Scrape pages sequentially to preserve relative order
            for page in range(0, limit + 1):
                batch = await crawl_page(session, sem, cat["source_id"], page)
                if not batch:
                    break
                    
                for a in batch:
                    # ตรวจจับหมวดหมู่
                    if cat["source_id"] == "HOME":
                        title = a["title"]
                        if "พากย์ไทย" in title: a["source_cat_id"] = "2"
                        elif "เดอะมูฟวี่" in title: a["source_cat_id"] = "3"
                        else: a["source_cat_id"] = "1"

                    a["sort_order"] = current_sort_index
                    current_sort_index -= 1
                    
                    if a["link"] not in seen_links:
                        seen_links.add(a["link"])
                        all_animes.append(a)
                
                print(f"  [+] สแกนหน้า {page} สำเร็จ (รวม {len(batch)} เรื่อง)...")
                if is_test: break

        print(f"\n📌 พบอนิเมะรวมทั้งหมด {len(all_animes)} เรื่อง")

        # ── [2/3] ดึง episode list ของทุกเรื่อง (เพือเช็คตอนใหม่) ──
        print(f"\n[2/3] กำลังตรวจสอบรายชื่อตอน ({len(all_animes)} เรื่อง)...")
        ep_list_tasks = [crawl_episodes(session, sem, a) for a in all_animes]
        
        done = 0
        total = len(ep_list_tasks)
        for coro in asyncio.as_completed(ep_list_tasks):
            await coro
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  [+] ตรวจสอบรายชื่อตอนสำเร็จ {done}/{total} เรื่อง...")

        # ── [2.5/3] จัดเตรียมคิวเจาะวิดีโอ (สแกนรายตอน) ──
        to_crack_video = []
        for a in all_animes:
            anime_link = a["link"]
            anime_cache = cache_map.get(anime_link, {})
            
            for ep in a["episodes"]:
                ep_title = ep["title"]
                # ถ้ามีในแคช และ URL ไม่ใช่ลิ้งค์เดิมของเว็บต้นทาง แสดงว่าเจาะแล้ว
                if ep_title in anime_cache:
                    ep["url"] = anime_cache[ep_title] # ใช้ข้อมูลเดิม (real_url)
                else:
                    to_crack_video.append(ep)

        print(f"\n[2.5/3] ตรวจพบตอนใหม่ที่เจาะต้องเจาะวิดีโอ {len(to_crack_video)} ตอน (จากทั้งหมด {sum(len(a['episodes']) for a in all_animes)} ตอน)...")

        if to_crack_video:
            video_tasks = [crawl_video(session, sem, ep) for ep in to_crack_video]
            done = 0
            total_eps = len(video_tasks)
            for coro in asyncio.as_completed(video_tasks):
                await coro
                done += 1
                if done % 200 == 0 or done == total_eps:
                    print(f"  [+] เจาะวิดีโอใหม่แล้ว {done}/{total_eps} ตอน...")
        else:
            print("✨ ทุกตอนถูกสแกนแล้วในแคช ไม่ต้องเจาะวิดีโอเพิ่ม")

    return all_animes


async def solve_test_cookie(session, html):
    """แกะรหัสเพื่อสร้าง __test cookie ของ InfinityFree"""
    try:
        # ล้างช่องว่างเพื่อให้ Regex จับง่ายขึ้น
        clean_html = html.replace(" ", "").replace("\n", "").replace("\r", "")
        # ตัวอย่าง: a=toNumbers("..."),b=toNumbers("..."),c=toNumbers("...")
        match = re.search(r'a=toNumbers\("([^"]+)"\),b=toNumbers\("([^"]+)"\),c=toNumbers\("([^"]+)"\)', clean_html)
        if not match:
            return None

        a_hex, b_hex, c_hex = match.groups()
        key = bytes.fromhex(a_hex)
        iv = bytes.fromhex(b_hex)
        ciphertext = bytes.fromhex(c_hex)

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(ciphertext)
        return decrypted.hex()
    except Exception as e:
        print(f"  [!] ไม่สามารถไขรหัสคุกกี้ได้: {e}")
        return None


async def push_to_api(export_data: dict):
    """ส่งข้อมูล JSON ไปที่เว็บไซต์ผ่าน API"""
    url = os.getenv("ADMIN_URL")
    key = os.getenv("SECRET_KEY")

    if not url or not key:
        print("\n❌ [Error] ไม่พบ ADMIN_URL หรือ SECRET_KEY ใน Environment Variables")
        return False

    # ตรวจสอบ URL ว่าลงท้ายด้วย ?page=admin&ajax_import=1 หรือยัง
    if "ajax_import=1" not in url:
        url = url.rstrip("/")
        if "?" in url: url += "&ajax_import=1"
        else: url += "?page=admin&ajax_import=1"

    print(f"\n🚀 กำลังส่งข้อมูลขึ้นเว็บ: {url}...")
    
    # แบ่งข้อมูลเป็น batches เล็กๆ เพื่อความปลอดภัย (ป้องกัน timeout/memory limit)
    all_batches = []
    BATCH_SIZE = 50
    for cat_id, cat_data in export_data.items():
        animes = cat_data.get("animes", [])
        for i in range(0, len(animes), BATCH_SIZE):
            chunk = animes[i : i + BATCH_SIZE]
            all_batches.append({cat_id: {"name": cat_data["name"], "animes": chunk}})

    headers = {
        "Content-Type": "application/json",
        "X-Admin-Key": key
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # --- ตรวจสอบตัวตน (Initial Check / Cookie Bypass) ---
        print(f"  [*] ตรวจสอบสถานะการเชื่อมต่อ...")
        async with session.get(url) as resp:
            resp_text = await resp.text()
            if "toNumbers" in resp_text:
                print("  [!] ตรวจพบระบบดัก Bot ของ InfinityFree! กำลังพยายามไขรหัส...")
                cookie_val = await solve_test_cookie(session, resp_text)
                if cookie_val:
                    session.cookie_jar.update_cookies({"__test": cookie_val})
                    print(f"  [+] ไขรหัสสำเร็จ! (Cookie: {cookie_val[:8]}...)")
                    # ทดสอบอีกรอบ
                    async with session.get(url) as resp2:
                        if "toNumbers" in await resp2.text():
                            print("  [-] ไขรหัสแล้วแต่ยังโดนบล็อก...")
                else:
                    print("  [-] ไขรหัสไม่สำเร็จ ระบบอาจมีการเปลี่ยนแปลง")

        # --- เริ่มส่งข้อมูลเป็น Batches ---
        for i, batch in enumerate(all_batches):
            try:
                async with session.post(url, json=batch, timeout=45) as resp:
                    resp_text = await resp.text()
                    try:
                        res_json = json.loads(resp_text)
                        if res_json.get("success"):
                            print(f"  [+] ชุดที่ {i+1}/{len(all_batches)} สำเร็จ! (อนิเมะ: {res_json.get('total_anime')})")
                        else:
                            print(f"  [-] ชุดที่ {i+1}/{len(all_batches)} ผิดพลาด: {res_json.get('message')}")
                    except Exception:
                        print(f"  [!] ชุดที่ {i+1}/{len(all_batches)}: Server ไม่ได้ส่ง JSON กลับมา (HTTP {resp.status})")
                        print(f"      ข้อความจาก Server (ย่อ): {resp_text[:300]}...")
            except Exception as e:
                print(f"  [!] เกิดข้อผิดพลาดในการเชื่อมต่อชุดที่ {i+1}: {e}")

    print("\n✅ การส่งข้อมูลเสร็จสิ้น!")
    return True


def save_to_file(animes: list) -> dict:
    """ สร้างไฟล์ anime_data.js เพื่อเอาไปอัปเดตผ่านหน้า Admin ในเว็บ """
    print(f"\n📂 กำลังสร้างไฟล์ข้อมูล 'anime_data.js'...")
    
    export_data = {}
    cat_names = {"1": "ซับไทย", "2": "พากย์ไทย", "3": "เดอะมูฟวี่"}
    
    for a in animes:
        sid = a["source_cat_id"]
        if sid == "HOME": continue # HOME is only for sorting
        if sid not in export_data:
            export_data[sid] = {
                "name": cat_names.get(sid, f"หมวด {sid}"),
                "animes": []
            }
        export_data[sid]["animes"].append({
            "title": a["title"],
            "link": a["link"],
            "cover": a["cover"],
            "sort_order": a.get("sort_order", 0),
            "episodes": a["episodes"]
        })

    # บันทึกเป็นไฟล์ .js (ยังเผื่อไว้ใช้แบบ manual)
    try:
        with open("anime_data.js", "w", encoding="utf-8") as f:
            f.write("const animeData = ")
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            f.write(";")
        print("\n✅ สร้างไฟล์ 'anime_data.js' เรียบร้อย")
    except Exception as e:
        print(f"❌ สร้างไฟล์ไม่สำเร็จ: {e}")
        
    return export_data


def main():
    parser = argparse.ArgumentParser(description="Anime Scraper — Ultra Edition")
    parser.add_argument("--auto", action="store_true", help="รันอัตโนมัติ (Fast Update + Auto Upload)")
    args = parser.parse_args()

    print("🚀 ระบบสแกน Anime — ⚡ ULTRA Edition")
    
    if args.auto:
        print("🤖 [MODE: AUTO] สแกนเรื่องใหม่และอัปโหลดขึ้นเว็บทันที...")
        is_test = False
        use_cache = True # Fast update
    else:
        print("1. 💥 Full Scan (สแกนทั้งหมด - ช้า)")
        print("2. 🧪 Test Mode (สแกนหน้าแรกเท่านั้น)")
        print("3. ⚡ Fast Update (สแกนเฉพาะเรื่องใหม่ - แนะนำ)")
        choice = input("👉 เลือก (1/2/3): ").strip()
        is_test = choice == "2"
        use_cache = choice == "3"

    categories = [
        {"source_id": "HOME", "name": "หน้าหลัก (อัปเดตล่าสุด)", "max_page": 535},
        {"source_id": "2", "name": "พากย์ไทย", "max_page": 300},
        {"source_id": "1", "name": "ซับไทย", "max_page": 300},
        {"source_id": "3", "name": "เดอะมูฟวี่", "max_page": 300}
    ]

    t0 = time.time()

    # รันการสแกนแบบ Async
    animes = asyncio.run(run_all(categories, is_test, use_cache))

    # จัดรูปข้อมูล
    export_data = save_to_file(animes)

    # ถ้าโหมดอัตโนมัติ ให้ยิง API ทันที
    if args.auto:
        asyncio.run(push_to_api(export_data))

    print(f"\n📊 ใช้เวลาสแกนทั้งหมด {time.time() - t0:.2f} วินาที")
    
    if not args.auto:
        input("\nกด Enter เพื่อปิด...")


if __name__ == "__main__":
    main()
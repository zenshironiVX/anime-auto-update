"""
scraper_anime.py — ⚡ ULTRA Edition (Fixed)
แก้ไขให้ตรงกับโครงสร้างเว็บ anime-hdzero.com จริง:
  - URL pattern ถูกต้อง (?page=N / ?page=N สำหรับ category)
  - CSS Selector ถูกต้อง (a.group.block, a.ep-row, iframe)
  - Decode BASE64 จาก player embed เพื่อดึง real URL
  - Logic แคชรายตอนที่ถูกต้อง
  - asyncio + aiohttp สำหรับ concurrency สูง
"""

import json
import os
import sys
import argparse
import asyncio
import aiohttp
import time
import base64
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urljoin

# ==================== ⚙️ CONFIG ====================
CONCURRENT_REQUESTS = 100   # จำนวน HTTP requests พร้อมกันสูงสุด
TIMEOUT_SECS        = 15    # timeout ต่อ request
MAX_RETRIES         = 3
CONNECTOR_LIMIT     = 150   # TCP connection pool size
BASE_URL            = "https://anime-hdzero.com"
# ====================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}

# ─────────────────────────────────────────────────────
#  HTTP layer  (async)
# ─────────────────────────────────────────────────────

async def fetch(session: aiohttp.ClientSession, sem: asyncio.Semaphore, url: str) -> str | None:
    """GET url พร้อม retry + semaphore คุม concurrency"""
    async with sem:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECS),
                    allow_redirects=True,
                ) as resp:
                    if resp.status == 200:
                        return await resp.text(errors="replace")
                    if resp.status == 429:
                        wait = 2 ** attempt
                        print(f"  [!] Rate limited — รอ {wait}s ...")
                        await asyncio.sleep(wait)
                        continue
                    # 404 / 5xx ฯลฯ
                    return None
            except asyncio.TimeoutError:
                if attempt == MAX_RETRIES:
                    return None
                await asyncio.sleep(attempt * 1.5)
            except Exception as e:
                if attempt == MAX_RETRIES:
                    return None
                await asyncio.sleep(attempt)
    return None


# ─────────────────────────────────────────────────────
#  URL builder — ถูกต้องตาม pattern เว็บจริง
# ─────────────────────────────────────────────────────

def build_list_url(source_id: str, page: int) -> str:
    """
    หน้าหลัก  : https://anime-hdzero.com/?page=1
    Category   : https://anime-hdzero.com/category/1?page=1
    """
    if source_id == "HOME":
        return f"{BASE_URL}/?page={page}"
    return f"{BASE_URL}/category/{source_id}?page={page}"


def make_absolute(href: str) -> str:
    """แปลง relative path → absolute URL"""
    if href.startswith("http"):
        return href
    return BASE_URL + href if href.startswith("/") else f"{BASE_URL}/{href}"


# ─────────────────────────────────────────────────────
#  Parse helpers  (sync, CPU-only)
# ─────────────────────────────────────────────────────

def parse_anime_list(html: str) -> list[dict]:
    """
    ดึงการ์ดอนิเมะจากหน้ารายการ
    โครงสร้าง: <a class="group block" href="/anime/6158">
                  <img ... alt="ชื่อ">
                  <span class="sticker">DUB</span>
                  <div class="font-display ...">ชื่อเรื่อง</div>
               </a>
    """
    soup = BeautifulSoup(html, "html.parser")
    out = []

    for card in soup.select("a.group.block"):
        href = card.get("href", "")
        if not href or "/anime/" not in href:
            continue

        # Title — ใช้ alt ของรูปเป็นหลัก (ครบสุด) แล้ว fallback ไป .font-display
        img = card.select_one("img")
        title = ""
        if img:
            title = img.get("alt", "").strip()
        if not title:
            title_div = card.select_one(".font-display")
            title = title_div.get_text(strip=True) if title_div else "ไม่มีชื่อ"

        cover = img.get("src", "") if img else ""
        # ถ้าเป็น srcset ที่มีหลาย URL ให้เอาอันแรก
        if not cover and img:
            srcset = img.get("srcset", "")
            if srcset:
                cover = srcset.split(",")[0].split()[0]

        # Badge: DUB / SUB / AIRING / MOVIE
        sticker = card.select_one(".sticker")
        badge = sticker.get_text(strip=True) if sticker else ""

        # จำนวนตอน / ประเภท
        ep_span = card.select_one(".font-mono span")
        ep_count = ep_span.get_text(strip=True) if ep_span else ""

        out.append({
            "title":    title,
            "link":     make_absolute(href),
            "cover":    cover,
            "badge":    badge,
            "ep_count": ep_count,
            "episodes": [],
            "source_cat_id": "",  # จะกำหนดทีหลัง
            "sort_order": 0,
        })
    return out


def detect_category(title: str, badge: str) -> str:
    """
    เดาหมวดหมู่จาก title + badge
      1 = ซับไทย
      2 = พากย์ไทย
      3 = เดอะมูฟวี่ / Movie
    """
    if badge == "MOVIE" or "movie" in title.lower() or "เดอะมูฟวี่" in title:
        return "3"
    if "พากย์ไทย" in title or badge == "DUB":
        return "2"
    return "1"  # ซับไทย (default)


def parse_episode_links(html: str, anime_link: str) -> list[dict]:
    """
    ดึงรายชื่อตอนจากหน้าอนิเมะ
    โครงสร้าง: <a class="ep-row ..." href="/anime/6158/episode/105689">
                  <span class="text-[13px]">Masked Rider Zeztz ตอนที่ 1 พากย์ไทย</span>
               </a>
    """
    soup = BeautifulSoup(html, "html.parser")
    eps = []

    for a in soup.select("a.ep-row"):
        href = a.get("href", "")
        if not href or "/episode/" not in href:
            continue
        span = a.select_one("span.text-\\[13px\\]") or a.find("span")
        title = span.get_text(strip=True) if span else href.split("/")[-1]
        eps.append({
            "title": title,
            "url":   make_absolute(href),
        })

    # sort ตามหมายเลขตอน (ถ้า URL มีตัวเลข episode ID)
    eps.sort(key=lambda e: int(re.search(r"/episode/(\d+)", e["url"]).group(1))
             if re.search(r"/episode/(\d+)", e["url"]) else 0)
    return eps


def decode_video_url(html: str) -> str | None:
    """
    เจาะ URL วิดีโอจริงจาก iframe embed
    โครงสร้าง:
      <iframe src="https://anime-hdzero.com/player/embed.php?link=BASE64_ENCODED_URL">

    Base64 decode → URL จริง เช่น
      https://akuma-player.xyz/play/b8d59412-...
    """
    soup = BeautifulSoup(html, "html.parser")

    # หา iframe ที่มี embed.php
    iframe = soup.find("iframe", src=re.compile(r"embed\.php\?link="))
    if not iframe:
        # fallback: หา iframe ทั่วไป
        iframe = soup.find("iframe")
    if not iframe:
        return None

    src = iframe.get("src", "")
    if not src:
        return None

    # ถ้าเป็น embed.php?link=BASE64 → decode
    parsed = urlparse(src)
    qs = parse_qs(parsed.query)
    if "link" in qs:
        b64 = qs["link"][0]
        # เติม padding ถ้าขาด
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        try:
            real_url = base64.b64decode(b64).decode("utf-8")
            if real_url.startswith("http"):
                return real_url
        except Exception:
            pass

    # ถ้า src เป็น URL ตรงๆ อยู่แล้ว
    if src.startswith("http"):
        return src
    return None


# ─────────────────────────────────────────────────────
#  Async pipeline
# ─────────────────────────────────────────────────────

async def crawl_list_page(session, sem, source_id: str, page: int) -> list[dict]:
    url = build_list_url(source_id, page)
    html = await fetch(session, sem, url)
    if not html:
        return []
    animes = parse_anime_list(html)

    # กำหนดหมวดหมู่
    for a in animes:
        if source_id == "HOME":
            a["source_cat_id"] = detect_category(a["title"], a["badge"])
        else:
            a["source_cat_id"] = source_id

    return animes


async def crawl_episodes(session, sem, anime: dict) -> None:
    """ดึง episode list ของอนิเมะ 1 เรื่อง"""
    html = await fetch(session, sem, anime["link"])
    if html:
        anime["episodes"] = parse_episode_links(html, anime["link"])


async def crawl_video(session, sem, ep: dict) -> None:
    """เจาะ real video URL ของ 1 ตอน"""
    html = await fetch(session, sem, ep["url"])
    if html:
        real = decode_video_url(html)
        if real:
            ep["url"] = real


# ─────────────────────────────────────────────────────
#  Cache loader
# ─────────────────────────────────────────────────────

def load_cache(path: str = "anime_data.js") -> dict:
    """
    โหลดไฟล์ anime_data.js เดิม แล้วสร้าง map:
      { anime_link: { ep_title: resolved_url } }
    """
    cache_map: dict[str, dict[str, str]] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        # ลบ const animeData = ... ; ครอบหน้า-หลัง
        text = re.sub(r"^\s*const\s+animeData\s*=\s*", "", text)
        text = re.sub(r";\s*$", "", text)
        old: dict = json.loads(text)

        for cat_data in old.values():
            for anime in cat_data.get("animes", []):
                a_link = anime.get("link", "")
                ep_map: dict[str, str] = {}
                for ep in anime.get("episodes", []):
                    url = ep.get("url", "")
                    title = ep.get("title", "")
                    # ถ้า URL ไม่ใช่ /episode/ แสดงว่าเจาะแล้ว (real URL)
                    if title and url and "/episode/" not in url:
                        ep_map[title] = url
                if a_link:
                    cache_map[a_link] = ep_map
        print(f"📦 โหลดแคชสำเร็จ: {len(cache_map)} เรื่อง")
    except FileNotFoundError:
        print("ℹ️  ไม่พบไฟล์แคช — เริ่มสแกนใหม่ทั้งหมด")
    except Exception as e:
        print(f"⚠️  โหลดแคชผิดพลาด: {e} — เริ่มสแกนใหม่")
    return cache_map


# ─────────────────────────────────────────────────────
#  Main async runner
# ─────────────────────────────────────────────────────

async def run_all(categories: list[dict], is_test: bool, use_cache: bool) -> list[dict]:
    cache_map = load_cache() if use_cache else {}

    sem       = asyncio.Semaphore(CONCURRENT_REQUESTS)
    connector = aiohttp.TCPConnector(
        limit=CONNECTOR_LIMIT,
        ttl_dns_cache=300,
        ssl=False,          # ลด overhead SSL verification
    )

    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:

        # ── [1/3] สแกนรายการอนิเมะจากทุก category ──
        all_animes: list[dict]     = []
        seen_links: set[str]       = set()
        sort_idx = 1_000_000

        for cat in categories:
            print(f"\n[1/3] สแกน: {cat['name']}")
            max_pg = 1 if is_test else cat["max_page"]

            for page in range(1, max_pg + 1):
                batch = await crawl_list_page(session, sem, cat["source_id"], page)
                if not batch:
                    print(f"  [!] หน้า {page} ไม่มีข้อมูล → หยุดสแกน category นี้")
                    break

                added = 0
                for a in batch:
                    link = a["link"]
                    if link not in seen_links:
                        seen_links.add(link)
                        a["sort_order"] = sort_idx
                        sort_idx -= 1
                        all_animes.append(a)
                        added += 1

                print(f"  [+] หน้า {page}: เพิ่ม {added} เรื่อง (รวม {len(all_animes)})")
                if is_test:
                    break

        print(f"\n📌 พบอนิเมะทั้งหมด {len(all_animes)} เรื่อง")

        # ── [2/3] ดึงรายชื่อตอนทุกเรื่อง ──
        print(f"\n[2/3] ดึงรายชื่อตอน ({len(all_animes)} เรื่อง)...")
        ep_tasks = [crawl_episodes(session, sem, a) for a in all_animes]
        done = 0
        for coro in asyncio.as_completed(ep_tasks):
            await coro
            done += 1
            if done % 50 == 0 or done == len(ep_tasks):
                print(f"  [+] {done}/{len(ep_tasks)} เรื่อง ดึงตอนสำเร็จ")

        # ── [2.5/3] ตรวจแคชรายตอน ──
        to_crack: list[dict] = []
        cached_count = 0

        for a in all_animes:
            anime_cache = cache_map.get(a["link"], {})
            for ep in a["episodes"]:
                if ep["title"] in anime_cache:
                    ep["url"] = anime_cache[ep["title"]]
                    cached_count += 1
                else:
                    to_crack.append(ep)

        total_eps = sum(len(a["episodes"]) for a in all_animes)
        print(f"\n📊 รวม {total_eps} ตอน | แคช: {cached_count} | ต้องเจาะใหม่: {len(to_crack)}")

        # ── [3/3] เจาะ URL วิดีโอ ──
        if to_crack:
            print(f"\n[3/3] เจาะ video URL ({len(to_crack)} ตอน)...")
            video_tasks = [crawl_video(session, sem, ep) for ep in to_crack]
            done = 0
            total = len(video_tasks)
            for coro in asyncio.as_completed(video_tasks):
                await coro
                done += 1
                if done % 200 == 0 or done == total:
                    print(f"  [+] เจาะวิดีโอ {done}/{total} ตอน")
        else:
            print("\n✨ ทุกตอนอยู่ในแคชแล้ว ไม่ต้องเจาะเพิ่ม")

    return all_animes


# ─────────────────────────────────────────────────────
#  Output: บันทึกไฟล์
# ─────────────────────────────────────────────────────

def save_to_file(animes: list[dict], path: str = "anime_data.js") -> dict:
    cat_names = {"1": "ซับไทย", "2": "พากย์ไทย", "3": "เดอะมูฟวี่"}
    export: dict[str, dict] = {}

    for a in animes:
        sid = a.get("source_cat_id", "1")
        if sid not in cat_names:
            sid = "1"
        if sid not in export:
            export[sid] = {"name": cat_names[sid], "animes": []}
        export[sid]["animes"].append({
            "title":      a["title"],
            "link":       a["link"],
            "cover":      a["cover"],
            "badge":      a.get("badge", ""),
            "sort_order": a.get("sort_order", 0),
            "episodes":   a["episodes"],
        })

    # เรียงตาม sort_order (ใหม่ก่อน = sort_order สูงกว่า)
    for sid in export:
        export[sid]["animes"].sort(key=lambda x: x["sort_order"], reverse=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("const animeData = ")
            json.dump(export, f, ensure_ascii=False, indent=2)
            f.write(";")
        total = sum(len(v["animes"]) for v in export.values())
        eps   = sum(len(ep) for v in export.values()
                    for a in v["animes"] for ep in [a["episodes"]])
        print(f"\n✅ บันทึก '{path}' เรียบร้อย | {total} เรื่อง | {eps} ตอน")
    except Exception as e:
        print(f"❌ บันทึกไฟล์ไม่สำเร็จ: {e}")

    return export


# ─────────────────────────────────────────────────────
#  API push (optional)
# ─────────────────────────────────────────────────────

async def push_to_api(export_data: dict):
    url = os.getenv("ADMIN_URL", "")
    key = os.getenv("SECRET_KEY", "")

    if not url or not key:
        print("\n❌ ไม่พบ ADMIN_URL หรือ SECRET_KEY ใน Environment Variables")
        return

    if "ajax_import=1" not in url:
        sep = "&" if "?" in url else "?"
        url = url.rstrip("/") + sep + "page=admin&ajax_import=1"

    print(f"\n🚀 กำลังส่งข้อมูลขึ้นเว็บ: {url}")
    headers_api = {
        "Content-Type":  "application/json",
        "X-Admin-Key":   key,
    }

    BATCH = 50
    batches: list[dict] = []
    for cat_id, cat_data in export_data.items():
        animes = cat_data["animes"]
        for i in range(0, len(animes), BATCH):
            chunk = animes[i:i + BATCH]
            batches.append({cat_id: {"name": cat_data["name"], "animes": chunk}})

    async with aiohttp.ClientSession(headers=headers_api) as session:
        for i, batch in enumerate(batches, 1):
            try:
                async with session.post(url, json=batch, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    text = await resp.text()
                    try:
                        res = json.loads(text)
                        status = "✅" if res.get("success") else "❌"
                        print(f"  {status} Batch {i}/{len(batches)}: {res.get('message', '')}")
                    except Exception:
                        print(f"  [!] Batch {i}/{len(batches)}: HTTP {resp.status} — {text[:200]}")
            except Exception as e:
                print(f"  [!] Batch {i}/{len(batches)} error: {e}")

    print("\n✅ ส่งข้อมูลเสร็จสิ้น!")


# ─────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────

# หมวดหมู่และจำนวนหน้าสูงสุดโดยประมาณ
CATEGORIES = [
    {"source_id": "HOME", "name": "หน้าหลัก (ล่าสุด)",  "max_page": 268},
    {"source_id": "2",    "name": "พากย์ไทย",             "max_page": 98},
    {"source_id": "1",    "name": "ซับไทย",               "max_page": 127},
    {"source_id": "3",    "name": "เดอะมูฟวี่",            "max_page": 44},
]


def main():
    parser = argparse.ArgumentParser(description="Anime Scraper — ULTRA Edition (Fixed)")
    parser.add_argument("--auto",       action="store_true", help="รันอัตโนมัติ (Fast Update + Upload)")
    parser.add_argument("--full",       action="store_true", help="Full Scan ไม่ใช้แคช")
    parser.add_argument("--test",       action="store_true", help="Test mode (หน้าแรกอย่างเดียว)")
    parser.add_argument("--no-upload",  action="store_true", help="อย่า push API")
    args = parser.parse_args()

    print("🚀 Anime Scraper — ⚡ ULTRA Edition (Fixed)\n")

    if args.auto:
        is_test   = False
        use_cache = True
        do_upload = not args.no_upload
        print("🤖 [AUTO] Fast Update + Auto Upload")
    elif args.test:
        is_test   = True
        use_cache = False
        do_upload = False
        print("🧪 [TEST] สแกนเฉพาะหน้าแรก")
    elif args.full:
        is_test   = False
        use_cache = False
        do_upload = not args.no_upload
        print("💥 [FULL] สแกนทั้งหมด ไม่ใช้แคช")
    else:
        print("เลือกโหมด:")
        print("  1 = 💥 Full Scan (ช้า, ไม่ใช้แคช)")
        print("  2 = 🧪 Test Mode (หน้าแรกอย่างเดียว)")
        print("  3 = ⚡ Fast Update (แนะนำ — ใช้แคช)")
        choice = input("👉 เลือก (1/2/3): ").strip()
        is_test   = choice == "2"
        use_cache = choice == "3"
        do_upload = False

    t0 = time.time()

    animes      = asyncio.run(run_all(CATEGORIES, is_test, use_cache))
    export_data = save_to_file(animes)

    if do_upload:
        asyncio.run(push_to_api(export_data))

    elapsed = time.time() - t0
    print(f"\n⏱  เวลาทั้งหมด: {elapsed:.1f} วินาที")

    if not (args.auto or args.full or args.test):
        input("\nกด Enter เพื่อปิด...")


if __name__ == "__main__":
    main()

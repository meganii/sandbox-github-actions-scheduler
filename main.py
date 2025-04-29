import asyncio
import aiohttp
import json
import os
import urllib.parse
import logging
import time
from datetime import datetime

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"scrapbox_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

project = "meganii"
dist_stats = f"./{project}/stats/pages.json"
dist_data = "./pages.jsonl"

concurrency_limit = 10  # 同時に実行する最大リクエスト数
sem = asyncio.Semaphore(concurrency_limit)


async def fetch_with_retry(session, url, retry_count=3, delay_sec=1):
    for i in range(retry_count):
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"Status {resp.status}")
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    raise Exception(f"Unexpected content-type: {content_type}")
                return await resp.json()
        except Exception as e:
            logger.warning(f"[retry {i+1}] Failed: {url} ({e})")
            if i < retry_count - 1:
                await asyncio.sleep(delay_sec * (i + 1))  # 指数バックオフ
            else:
                logger.error(f"Failed after {retry_count} retries: {url}")
                raise


async def fetch_summary(session):
    url = f"https://scrapbox.io/api/pages/{project}/?limit=1"
    logger.info(f"Fetching project summary: {url}")
    data = await fetch_with_retry(session, url)
    logger.info(f"Total pages in project: {data['count']}")
    return data["count"]


async def fetch_all_titles(session, total_pages, limit=1000):
    pages = []
    max_index = (total_pages // limit) + 1
    for i in range(max_index):
        skip = i * limit
        url = f"https://scrapbox.io/api/pages/{project}/?limit={limit}&skip={skip}"
        logger.info(f"Fetching page list: skip={skip}, limit={limit}")
        data = await fetch_with_retry(session, url)
        pages.extend(data["pages"])
        remaining = total_pages - (skip + len(data["pages"]))
        logger.info(f"Fetched {len(data['pages'])} pages, {remaining} remaining")
        if remaining > 0:
            # レート制限を避けるため待機
            await asyncio.sleep(2)
    return [{
        "id": page["id"],
        "title": page["title"],
        "created": page["created"],
        "updated": page["updated"],
        "image": page.get("image"),
        "descriptions": page.get("descriptions")
    } for page in pages]


async def fetch_page_detail_limited(session, page_info, index, total):
    title_encoded = urllib.parse.quote(page_info["title"], safe='')
    url = f"https://scrapbox.io/api/pages/{project}/{title_encoded}"
    
    try:
        async with sem:
            logger.info(f"[{index+1}/{total}] Fetching: {page_info['title']}")
            data = await fetch_with_retry(session, url)
            # レート制限を避けるため短い待機を入れる
            await asyncio.sleep(0.2)
            return {
                "id": data["id"],
                "title": data["title"],
                "created": data["created"],
                "updated": data["updated"],
                "lines": data["lines"]
            }
    except Exception as e:
        logger.error(f"Error fetching {page_info['title']}: {e}")
        # エラー時にも基本情報は返す
        return {
            "id": page_info["id"],
            "title": page_info["title"],
            "created": page_info["created"],
            "updated": page_info["updated"],
            "error": str(e),
            "lines": []
        }


async def main():
    start_time = time.time()
    logger.info(f"Starting backup of Scrapbox project: {project}")
    
    try:
        # ディレクトリ作成
        os.makedirs(os.path.dirname(dist_stats), exist_ok=True)
        
        async with aiohttp.ClientSession() as session:
            # プロジェクト情報取得
            count = await fetch_summary(session)
            
            # タイトル一覧取得
            titles = await fetch_all_titles(session, count)
            titles.sort(key=lambda x: x["created"])
            
            # メタデータ保存
            with open(dist_stats, "w", encoding="utf-8") as f:
                json.dump({
                    "projectName": project,
                    "count": count,
                    "pages": titles,
                    "backupDate": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"Metadata saved to {dist_stats}")

            # ページ詳細取得
            total = len(titles)
            logger.info(f"Fetching {total} page details...")
            
            tasks = [
                fetch_page_detail_limited(session, title, i, total)
                for i, title in enumerate(titles)
            ]
            results = await asyncio.gather(*tasks)
            
            # 結果をJSONLで保存
            with open(dist_data, "w", encoding="utf-8") as f:
                for item in results:
                    if "error" not in item:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    else:
                        logger.warning(f"Skipped writing page with error: {item['title']}")
            
            # 統計情報
            success_count = sum(1 for r in results if "error" not in r)
            error_count = sum(1 for r in results if "error" in r)
            logger.info(f"✅ JSON Lines written to {dist_data}")
            logger.info(f"Successfully backed up {success_count} pages")
            if error_count > 0:
                logger.warning(f"Failed to backup {error_count} pages")
    
    except Exception as e:
        logger.error(f"Backup failed: {e}", exc_info=True)
    
    finally:
        duration = time.time() - start_time
        logger.info(f"Backup process completed in {duration:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
# src/cosense_api.py
import asyncio
import aiohttp
import urllib.parse
# logger_config から設定済みロガーをインポート
from logger_config import logger
# config から設定値をインポート
import config

class CosenseAPIClient:
    BASE_URL = "https://scrapbox.io/api"

    def __init__(self, project, session):
        """CosenseAPIClientを初期化します。

        Args:
            project (str): 対象のCosenseプロジェクト名。
            session (aiohttp.ClientSession): 使用するaiohttpセッション。
        """
        self.project = project
        self.session = session
        # config から並行処理数を取得
        self.semaphore = asyncio.Semaphore(config.CONCURRENCY_LIMIT)
        logger.info(f"Initialized CosenseAPIClient for project: {self.project} (Concurrency Limit: {config.CONCURRENCY_LIMIT})")

    async def _fetch_with_retry(self, url, retry_count=3, delay_sec=1):
        """リトライロジック付きで指定されたURLからJSONデータを非同期に取得します。

        指数バックオフを使用してリトライします。
        404エラーはリトライせず、ClientResponseErrorを送出します。
        JSON以外のContent-Typeの場合は例外を送出します。

        Args:
            url (str): 取得対象のURL。
            retry_count (int, optional): 最大リトライ回数。デフォルトは3。
            delay_sec (int, optional): リトライ間の基本待機時間(秒)。デフォルトは1。

        Returns:
            dict: 取得したJSONデータ。

        Raises:
            aiohttp.ClientResponseError: 404エラーやリトライ後のHTTPエラーが発生した場合。
            Exception: JSONデコードエラーや予期せぬエラーが発生した場合。
        """
        for i in range(retry_count):
            try:
                logger.debug(f"Fetching URL (attempt {i+1}/{retry_count}): {url}")
                async with self.session.get(url) as resp:
                    logger.debug(f"URL: {url}, Status: {resp.status}, Content-Type: {resp.headers.get('Content-Type', '')}")

                    # 404 Not Found はリトライせずに即時エラーとする
                    if resp.status == 404:
                         logger.warning(f"Resource not found (404): {url}")
                         # aiohttp標準のエラーを送出
                         resp.raise_for_status()

                    # その他の非200ステータスコードの場合
                    elif resp.status != 200:
                        logger.warning(f"Non-200 status code {resp.status} received from {url}. Retrying if possible...")
                        resp.raise_for_status() # これにより ClientResponseError が発生し、リトライ対象となる

                    # Content-TypeがJSONかチェック
                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" not in content_type:
                        logger.error(f"Unexpected content-type received from {url}: {content_type}")
                        raise Exception(f"Unexpected content-type: {content_type}")

                    # 問題なければJSONをデコードして返す
                    return await resp.json()

            except aiohttp.ClientError as e: # aiohttp のクライアントエラー (接続エラー、タイムアウト、4xx/5xxエラーなど)
                logger.warning(f"[retry {i+1}/{retry_count}] Client error fetching {url}: {e}")
                last_exception = e
                if i < retry_count - 1:
                    # 指数バックオフで待機
                    await asyncio.sleep(delay_sec * (2 ** i)) # 1, 2, 4 秒...
                else:
                    logger.error(f"Failed after {retry_count} retries due to client error: {url}")
                    raise last_exception # 最後に発生した例外を再送出

            except Exception as e: # JSONデコードエラーやその他の予期せぬ例外
                 logger.warning(f"[retry {i+1}/{retry_count}] Unexpected error fetching {url}: {e}", exc_info=True) # 詳細ログ
                 last_exception = e
                 if i < retry_count - 1:
                    await asyncio.sleep(delay_sec * (2 ** i))
                 else:
                    logger.error(f"Failed after {retry_count} retries due to unexpected error: {url}")
                    raise last_exception

    async def fetch_page_count(self):
        """プロジェクトのページ総数を取得します。

        Returns:
            int: プロジェクトの総ページ数。

        Raises:
            ValueError: レスポンス形式が不正な場合。
            Exception: APIリクエストに失敗した場合。
        """
        url = f"{self.BASE_URL}/pages/{self.project}/?limit=1"
        logger.info(f"Fetching CoSense project summary from: {url}")
        try:
            data = await self._fetch_with_retry(url)
            count = data.get("count")
            if count is None:
                 logger.error(f"Could not find 'count' in summary response from {url}. Response: {data}")
                 raise ValueError("Invalid summary response format: 'count' key missing.")
            logger.info(f"Total pages in CoSense project '{self.project}': {count}")
            return count
        except Exception as e:
            logger.error(f"Failed to fetch CoSense project summary for '{self.project}': {e}", exc_info=True)
            raise

    async def fetch_all_titles(self, total_pages, limit=1000):
        """プロジェクト内の全ページの基本情報（ID, title, created, updatedなど）を取得します。

        Args:
            total_pages (int): 取得対象の総ページ数 (fetch_summaryの結果など)。
            limit (int, optional): 1リクエストあたりの取得件数上限。デフォルトは1000。

        Returns:
            list[dict]: 各ページの基本情報を含む辞書のリスト。
                        取得に失敗した場合は、それまでに取得できたリストを返す可能性があります。
        """
        pages_metadata = []
        fetched_count = 0
        # ページ数が0の場合、APIコールせずに空リストを返す
        if total_pages == 0:
             logger.info(f"CoSense project '{self.project}' has 0 pages. Skipping title fetching.")
             return []

        # 必要なAPIリクエスト回数を計算 (total_pages / limit の切り上げ)
        max_index = (total_pages + limit - 1) // limit

        logger.info(f"Fetching all page titles for CoSense project '{self.project}' ({total_pages} pages expected, batch size {limit})...")
        for i in range(max_index):
            skip = i * limit
            url = f"{self.BASE_URL}/pages/{self.project}/?limit={limit}&skip={skip}"
            logger.info(f"Fetching page list batch {i+1}/{max_index}: skip={skip}, limit={limit}")
            try:
                data = await self._fetch_with_retry(url)
                current_batch_pages = data.get("pages", [])
                if not current_batch_pages and skip < total_pages: # 最後のバッチ以外で空なら警告
                    logger.warning(f"Received empty 'pages' list for batch {i+1}/{max_index} from {url}, although more pages were expected.")

                # 必要なキーだけを安全に抽出
                for page in current_batch_pages:
                    pages_metadata.append({
                        "id": page.get("id"),
                        "title": page.get("title"),
                        "created": page.get("created"),
                        "updated": page.get("updated")
                    })
                fetched_count += len(current_batch_pages)
                remaining = total_pages - fetched_count
                logger.info(f"Fetched {len(current_batch_pages)} pages in this batch ({fetched_count}/{total_pages} total fetched), approximately {max(0, remaining)} remaining.")

                # APIサーバーへの負荷軽減のため、リクエスト間に短い待機を入れる (最後のバッチを除く)
                if i < max_index - 1:
                    await asyncio.sleep(1.0) # 1秒待機

            except Exception as e:
                logger.error(f"Failed to fetch page list batch {i+1}/{max_index} (skip={skip}): {e}", exc_info=True)
                # エラーが発生しても、それまでに取得したデータで処理を続行するか、ここで中断するか選択可能
                logger.warning("Continuing title fetching despite error in a batch. Result might be incomplete.")
                # raise # ここで raise すれば処理全体が止まる

        logger.info(f"Finished fetching titles for CoSense project '{self.project}'. Total metadata items collected: {len(pages_metadata)}")
        # 取得件数と期待件数に差異があれば警告
        if fetched_count != total_pages:
             logger.warning(f"Expected {total_pages} pages, but fetched metadata for {fetched_count} pages. Some pages might be missing or API returned unexpected count.")

        return pages_metadata

    async def fetch_page_detail(self, page_title, index=0, total=0):
        """指定されたページ情報に基づいて、ページの詳細（本文含む）を取得します。

        セマフォを使用して同時リクエスト数を制限します。

        Args:
            page_title (object): ページのtitle
            index (int, optional): 処理中のインデックス（ログ出力用）。デフォルトは0。
            total (int, optional): 処理全体の総数（ログ出力用）。デフォルトは0。

        Returns:
            dict: ページ詳細情報を含む辞書。
                  取得に失敗した場合は、'error' キーを含む辞書を返します。
        """
        if not page_title:
            logger.error(f"Invalid page_info provided: missing or empty title. page_info ID={page_title}")

        # URLエンコード (安全な文字以外をエンコード)
        title_encoded = urllib.parse.quote(page_title, safe='')
        url = f"{self.BASE_URL}/pages/{self.project}/{title_encoded}"

        log_prefix = f"[{index+1}/{total}] " if total > 0 else ""

        try:
            # セマフォで同時実行数を制限
            async with self.semaphore:
                logger.info(f"{log_prefix}Fetching detail: {page_title}")
                logger.debug(f"{log_prefix}Fetching URL: {url}")
                data = await self._fetch_with_retry(url)
                # API負荷軽減のため、リクエスト成功後に短い待機
                await asyncio.sleep(1) # 1秒待機
                # 正常な場合の返り値
                return data
        except aiohttp.ClientResponseError as e:
             # HTTPエラーを個別にハンドル
             if e.status == 404:
                  logger.warning(f"{log_prefix}Page not found (404): {page_title} at {url}")
                  error_message = f"Page not found (404)"
             else:
                  logger.error(f"{log_prefix}HTTP error fetching detail for '{page_title}': {e.status} {e.message}", exc_info=False)
                  error_message = f"HTTP Error {e.status}: {e.message}"
             # エラー時にも基本情報は返す (エラー情報付きで)
             return {
                "title": page_title,
                "error": error_message
             }
        except Exception as e:
            # その他の予期せぬエラー
            logger.error(f"{log_prefix}Unexpected error fetching detail for '{page_title}': {e}", exc_info=True)
            return {
                "title": page_title,
                "error": str(e)
            }

    async def fetch_multiple_page_details(self, page_infos):
        """複数のページ詳細情報を並行して非同期に取得します。

        Args:
            page_infos (list[object]): 各ページの基本情報オブジェクトのリスト。
                                       各オブジェクトは fetch_page_detail が要求する属性を持つ必要があります。

        Returns:
            list[dict]: 各ページの取得結果（詳細情報またはエラー情報）のリスト。
                        入力リストと同じ順序で返されます。
        """
        total = len(page_infos)
        if total == 0:
            logger.info("No page details to fetch.")
            return []

        logger.info(f"Fetching details for {total} pages concurrently (limit: {config.CONCURRENCY_LIMIT})...")
        # 各ページの詳細取得タスクを作成
        tasks = [self.fetch_page_detail(page_info.title, i, total) for i, page_info in enumerate(page_infos)]

        # asyncio.gather ですべてのタスクの完了を待つ
        # return_exceptions=True にすると、タスク内で例外が発生しても gather は停止せず、
        # 結果リストの中に例外オブジェクトそのものが含まれる。エラー処理に便利。
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 結果を処理（例外が発生した場合はエラー情報に変換）
        processed_results = []
        success_count = 0
        error_count = 0
        for i, result in enumerate(results):
            original_page_info = page_infos[i] # 対応する入力情報を取得
            if isinstance(result, Exception):
                # gather で例外がキャッチされた場合
                logger.error(f"Task for page '{getattr(original_page_info, 'title', 'N/A')}' failed with exception: {result}", exc_info=False)
                error_count += 1
                processed_results.append({
                    "id": getattr(original_page_info, 'id', None),
                    "title": getattr(original_page_info, 'title', 'N/A'),
                    "created": getattr(original_page_info, 'created', None),
                    "updated": getattr(original_page_info, 'updated', None),
                    "error": f"Task failed: {type(result).__name__}: {result}",
                    "lines": []
                })
            elif isinstance(result, dict) and result.get("error"):
                # fetch_page_detail がエラーdictを返した場合
                error_count += 1
                processed_results.append(result) # そのまま追加
            elif isinstance(result, dict):
                 # 正常に取得できた場合
                 success_count +=1
                 processed_results.append(result)
                 # 必要なら警告もチェック
                 if result.get("warning"):
                      logger.warning(f"Page '{result.get('title')}' fetched with warning: {result.get('warning')}")
            else:
                 # 予期せぬ結果型 (通常は発生しないはず)
                 logger.error(f"Unexpected result type for page '{getattr(original_page_info, 'title', 'N/A')}': {type(result)}")
                 error_count += 1
                 processed_results.append({
                    "id": getattr(original_page_info, 'id', None),
                    "title": getattr(original_page_info, 'title', 'N/A'),
                    "created": getattr(original_page_info, 'created', None),
                    "updated": getattr(original_page_info, 'updated', None),
                    "error": f"Unexpected result type: {type(result)}",
                    "lines": []
                 })


        logger.info(f"Finished fetching {total} page details. Success: {success_count}, Errors: {error_count}")
        return processed_results


if __name__ == "__main__":
     pass # ライブラリとして使われるため、通常は何も実行しない
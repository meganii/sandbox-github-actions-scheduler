# src/main.py
import asyncio
import aiohttp
import time
import json

# --- 自作モジュールのインポート ---
import config
from logger_config import logger
from cosense_api import CosenseAPIClient
from database import DataHandler

async def main_async():
    """CoSense バックアップ処理のメイン非同期関数"""
    start_time = time.time()
    logger.info(f"Starting CoSense backup process for project: {config.PROJECT}")

    # --- データベースハンドラの初期化 ---
    # config.DATABASE_PATH を使用してインメモリかファイルDBかを決定
    try:
        db_handler = DataHandler(db_path=config.DATABASE_PATH)
        logger.info(f"Initialized DataHandler with database: {config.DATABASE_PATH}")
    except Exception as e:
        logger.critical(f"Failed to initialize DataHandler: {e}", exc_info=True)
        return # DBハンドラがなければ処理を続けられない

    try:
        # --- aiohttp セッションの作成 ---
        # タイムアウト設定などを追加する場合はここに ClientTimeout を指定
        # timeout = aiohttp.ClientTimeout(total=60) # 例: 全体で60秒
        async with aiohttp.ClientSession() as session:
            logger.info("Created aiohttp ClientSession.")

            # --- CoSense API クライアントの初期化 ---
            api_client = CosenseAPIClient(config.PROJECT, session)
            logger.info("Initialized CosenseAPIClient.")

            # --- 最新のページリストをAPIから取得して保存する場合 ---
            logger.info("--- Fetching latest page list from CoSense API ---")
            try:
                total_pages = await api_client.fetch_page_count()
                if total_pages > 0:
                    titles_metadata = await api_client.fetch_all_titles(total_pages)
                    titles_metadata.sort(key=lambda x: x.get("created", 0)) # created キーでソート
                    # JSONL 形式で config.PAGE_LIST_FILE に保存
                    with open(config.PAGE_LIST_FILE, 'w', encoding='utf-8') as f:
                        for item in titles_metadata:
                            # titleがNoneでないことを確認（APIからの異常データ対策）
                            if item.get("title") is not None:
                                 f.write(json.dumps(item, ensure_ascii=False) + "\n")
                            else:
                                 logger.warning(f"Skipping metadata item with missing title: ID={item.get('id')}")
                    logger.info(f"Saved {len(titles_metadata)} page metadata items to {config.PAGE_LIST_FILE}")
                else:
                    logger.info("Project has 0 pages, skipping page list saving.")
            except Exception as e:
                logger.error(f"Failed to fetch and save latest page list: {e}", exc_info=True)
                logger.warning("Proceeding with existing page list file (if available).")
            logger.info("--- Finished fetching latest page list ---")

            # --- データベースに初期データをロード ---
            logger.info("--- Loading initial data into database ---")
            try:
                db_handler.load_initial_data()
                logger.info("Successfully loaded initial data.")
            except FileNotFoundError as e:
                 logger.critical(f"Required data file not found: {e}. Cannot proceed.")
                 logger.critical(f"Ensure '{config.PAGE_LIST_FILE}' exists.")
                 logger.critical(f"If '{config.PAGES_DATA_FILE}' is missing and this is the first run, it might be okay.")
                 return # 必須ファイルがない場合は終了
            except Exception as e:
                logger.critical(f"Failed to load initial data: {e}", exc_info=True)
                return # データロード失敗は致命的

            # --- 更新・新規レコードの特定 ---
            logger.info("--- Identifying changes (updates, inserts, deletes) ---")
            update_targets = db_handler.find_updated_records()
            insert_targets = db_handler.find_inserted_records()
            # 削除対象も特定 (apply_changes 内で使われる)
            deleted_targets_df = db_handler.find_deleted_records_ids()
            logger.info(f"Found {len(update_targets)} pages to update, {len(insert_targets)} new pages, and {len(deleted_targets_df)} pages to delete.")

            # --- 更新が必要なページの詳細を取得 ---
            update_results = []
            if not update_targets.empty:
               logger.info(f"--- Fetching details for {len(update_targets)} pages to update ---")
               # DataFrame の各行を fetch_multiple_page_details が受け取れるオブジェクト (名前付きタプル) に変換
               # itertuples(index=False) を使うと効率的
               update_target_infos = list(update_targets.itertuples(index=False, name="PageInfo"))
               update_results = await api_client.fetch_multiple_page_details(update_target_infos)
               logger.info(f"Finished fetching details for pages to update.")

            # --- 新規ページの詳細を取得 ---
            insert_results = []
            if not insert_targets.empty:
                logger.info(f"--- Fetching details for {len(insert_targets)} new pages ---")
                new_target_infos = list(insert_targets.itertuples(index=False, name="PageInfo"))
                insert_results = await api_client.fetch_multiple_page_details(new_target_infos)
                logger.info(f"Finished fetching details for new pages.")

            # --- データベースに変更を適用 ---
            logger.info("--- Applying changes to the database ---")
            try:
                # 引数でファイルパスを渡す必要はない (DataHandler内部でconfig参照)
                db_handler.apply_changes(update_results, insert_results)
                logger.info("Successfully applied changes to the database.")
            except Exception as e:
                 logger.error(f"Failed to apply changes to the database: {e}", exc_info=True)
                 # エラーが発生した場合でも、Parquetエクスポートを試みるか、ここで終了するか選択
                 # logger.warning("Attempting to export current database state despite apply_changes error...")
                 # raise # ここで再送出すれば finally に飛ぶ

            # --- 結果をParquetファイルにエクスポート ---
            logger.info("--- Exporting final data to Parquet file ---")
            try:
                # config で定義されたパスへエクスポート
                db_handler.export_to_parquet(config.PAGES_DATA_FILE)
                logger.info(f"Successfully exported data to {config.PAGES_DATA_FILE}")
            except Exception as e:
                 logger.error(f"Failed to export data to Parquet: {e}", exc_info=True)

            # --- 最終的な統計情報ログ (オプション) ---
            # final_success_updates = sum(1 for r in update_results if r and "error" not in r)
            # final_error_updates = len(update_results) - final_success_updates
            # final_success_inserts = sum(1 for r in insert_results if r and "error" not in r)
            # final_error_inserts = len(insert_results) - final_success_inserts
            # logger.info(f"Summary: Updates Fetched (Success/Error): {final_success_updates}/{final_error_updates}")
            # logger.info(f"Summary: Inserts Fetched (Success/Error): {final_success_inserts}/{final_error_inserts}")
            # logger.info(f"Summary: Deletions Applied: {len(deleted_targets_df)}") # apply_changes内で削除される

    except aiohttp.ClientError as e:
        logger.critical(f"HTTP Client Error during backup process: {e}", exc_info=True)
    except FileNotFoundError as e: # load_initial_data で捕捉されなかった場合など
        logger.critical(f"Prerequisite file not found: {e}")
    except Exception as e:
        # 予期せぬエラー
        logger.critical(f"An unexpected error occurred during the backup process: {e}", exc_info=True)

    finally:
        # --- DB接続を閉じる ---
        if 'db_handler' in locals() and db_handler:
            try:
                db_handler.close()
                logger.info("Closed database connection.")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}", exc_info=True)

        # --- 処理時間と終了ログ ---
        duration = time.time() - start_time
        logger.info(f"CoSense backup process finished in {duration:.2f} seconds.")


if __name__ == "__main__":
    # このスクリプトが直接実行された場合に main_async 関数を呼び出す
    # uv run python -m src.main または python -m src.main で実行
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user (KeyboardInterrupt).")
        # 必要ならここでもリソースクリーンアップ処理を追加
        sys.exit(1) # 中断されたことがわかるように終了コードを設定
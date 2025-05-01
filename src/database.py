# src/database.py
import duckdb
import pandas as pd
import os
import json
# logger_config から設定済みロガーをインポート
from logger_config import logger
# config から設定値をインポート
import config

class DataHandler:
    """DuckDBを使用してCoSenseページデータの永続化、差分検出、更新を行うクラス。"""

    def __init__(self, db_path=config.DATABASE_PATH):
        """DataHandlerを初期化し、DuckDBに接続します。

        Args:
            db_path (str, optional): DuckDBデータベースファイルのパス、または ':memory:'。
                                     デフォルトは config.DATABASE_PATH。
        """
        self.db_path = db_path
        try:
            self.con = duckdb.connect(database=self.db_path, read_only=False)
            logger.info(f"Connected to DuckDB database: {self.db_path}")
        except Exception as e:
            logger.critical(f"Failed to connect to DuckDB database at {self.db_path}: {e}", exc_info=True)
            # 接続に失敗した場合、後続のメソッドでエラーが発生するように None を設定するか、
            # ここで例外を再送出するかを選択できます。ここでは None を設定します。
            self.con = None
            raise # 接続失敗は致命的なので再送出する方が良い場合が多い

    def close(self):
        """DuckDB接続を閉じます。"""
        if self.con:
            try:
                self.con.close()
                logger.info(f"Closed DuckDB connection to {self.db_path}")
            except Exception as e:
                logger.error(f"Error closing DuckDB connection: {e}", exc_info=True)
        else:
             logger.warning("Attempted to close an already non-existent DB connection.")


    def _execute(self, sql, parameters=None, description="Executing SQL"):
        """SQLクエリを実行し、簡単なログを出力します。"""
        if not self.con:
            logger.error(f"Cannot {description}: Database connection is not available.")
            raise ConnectionError("Database connection is not available.") # 接続がない場合はエラー

        logger.debug(f"{description}: {sql} | Params: {parameters}")
        try:
            if parameters:
                return self.con.execute(sql, parameters)
            else:
                return self.con.execute(sql)
        except Exception as e:
            logger.error(f"Database error during '{description}': {e}", exc_info=True)
            logger.error(f"Failed SQL: {sql} | Params: {parameters}")
            raise # DBエラーは呼び出し元に伝える

    def _create_table_from_parquet(self, table_name, file_path):
        """Parquetファイルからテーブルを作成または置換します。"""
        sql = f'CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet($1)'
        self._execute(sql, [file_path], description=f"Creating table '{table_name}' from Parquet")
        # Parquetから読み込んだデータに主キーを設定
        try:
             self.con.sql(f'ALTER TABLE {table_name} ADD PRIMARY KEY (id)')
             logger.info(f"Set PRIMARY KEY on 'id' for table '{table_name}'.")
        except Exception as e:
            # id列がない、またはNULLが含まれるなどで失敗する可能性
             logger.warning(f"Could not set PRIMARY KEY on 'id' for table '{table_name}': {e}. Ensure 'id' column exists and contains unique, non-NULL values.")
        # self.con.sql(f'DESCRIBE {table_name}').show() # デバッグ用

    def _create_table_from_jsonl(self, table_name, file_path, columns_def=None):
        """JSONLファイルからテーブルを作成または置換します。"""
        # JSONパーサーのオプションを設定 (エラーが多い場合に調整)
        # options = ", ignore_errors=true" # エラー行を無視する場合
        options = ""

        if columns_def:
            # カラム定義がある場合 (より厳密)
            sql = f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_json($1, format='newline_delimited', columns={columns_def}{options})"
        else:
            # カラム定義がない場合 (自動推論)
            sql = f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_json_auto($1, format='newline_delimited'{options})"

        self._execute(sql, [file_path], description=f"Creating table '{table_name}' from JSONL")

        # JSON由来のテーブルに主キー設定を試みる
        try:
            self.con.sql(f'ALTER TABLE {table_name} ADD PRIMARY KEY (id)')
            logger.info(f"Set PRIMARY KEY on 'id' for table '{table_name}'.")
        except Exception as e:
            logger.warning(f"Could not set PRIMARY KEY on 'id' for table '{table_name}' derived from JSONL: {e}. Ensure 'id' column exists and contains unique, non-NULL values.")
        # self.con.sql(f'DESCRIBE {table_name}').show() # デバッグ用

    def load_initial_data(self):
        """初期データ（ページリストと既存ページデータ）をDBにロードします。"""
        logger.info(f"Loading initial data. Page list: '{config.PAGE_LIST_FILE}', Existing pages: '{config.PAGES_DATA_FILE}'")

        # 1. 既存ページデータ (Parquet) を 'pages' テーブルにロード
        if os.path.exists(config.PAGES_DATA_FILE):
            try:
                self._create_table_from_parquet('pages', config.PAGES_DATA_FILE)
                count = self.con.table('pages').count('*').fetchone()[0]
                logger.info(f"Loaded {count} records into 'pages' table from {config.PAGES_DATA_FILE}")
            except Exception as e:
                logger.error(f"Failed to load data from {config.PAGES_DATA_FILE}: {e}", exc_info=True)
                raise # Parquetロード失敗は問題なので上に伝える
        else:
            logger.warning(f"Existing pages data file not found: {config.PAGES_DATA_FILE}. Creating empty 'pages' table.")
            # 存在しない場合は空のテーブルを作成 (スキーマはParquetに基づくと仮定)
            # スキーマを正確に定義する必要がある
            schema_sql = """
            CREATE OR REPLACE TABLE pages (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                created BIGINT,
                updated BIGINT,
                lines STRUCT(id VARCHAR, userId VARCHAR, "text" VARCHAR, created BIGINT, updated BIGINT)[]
            );
            """
            self._execute(schema_sql, description="Creating empty 'pages' table")

        # 2. 最新ページリスト (JSONL) を 'pagelist' テーブルにロード
        if os.path.exists(config.PAGE_LIST_FILE):
            try:
                # カラム定義を指定しない (自動推論)
                self._create_table_from_jsonl('pagelist', config.PAGE_LIST_FILE)
                count = self.con.table('pagelist').count('*').fetchone()[0]
                logger.info(f"Loaded {count} records into 'pagelist' table from {config.PAGE_LIST_FILE}")
            except Exception as e:
                logger.error(f"Failed to load data from {config.PAGE_LIST_FILE}: {e}", exc_info=True)
                raise # こちらも失敗は問題
        else:
            # page_list.jsonl は通常必須
            logger.critical(f"Page list file not found: {config.PAGE_LIST_FILE}. This file is required to determine changes.")
            raise FileNotFoundError(f"Page list file not found: {config.PAGE_LIST_FILE}")

    def find_updated_records(self):
        """更新が必要なレコード（pagelistにあってpagesにもあり、updatedが新しい）を特定し、DataFrameで返します。"""
        sql = """
        SELECT pl.id, pl.title, pl.created, pl.updated
        FROM pagelist AS pl INNER JOIN pages AS p ON pl.id = p.id
        WHERE pl.updated > p.updated;
        """
        logger.info("Finding records to update...")
        df = self._execute(sql, description="Finding updated records").df()
        logger.info(f"Found {len(df)} records to update.")
        return df

    def find_inserted_records(self):
        """新規に追加されたレコード（pagelistにあってpagesにない）を特定し、DataFrameで返します。"""
        sql = """
        SELECT pl.id, pl.title, pl.created, pl.updated
        FROM pagelist AS pl LEFT JOIN pages AS p ON pl.id = p.id
        WHERE p.id IS NULL;
        """
        logger.info("Finding new records...")
        df = self._execute(sql, description="Finding new records").df()
        logger.info(f"Found {len(df)} new records.")
        return df

    def find_deleted_records_ids(self):
        """削除されたレコード（pagesにあってpagelistにない）のIDリストを返します。"""
        sql = """
        SELECT p.id
        FROM pages AS p LEFT JOIN pagelist AS pl ON p.id = pl.id
        WHERE pl.id IS NULL;
        """
        logger.info("Finding deleted records...")
        # df()ではなくfetchone()やfetchall()を使う方が効率的な場合がある
        result = self._execute(sql, description="Finding deleted records IDs").fetchall()
        deleted_ids = [row[0] for row in result]
        logger.info(f"Found {len(deleted_ids)} records to delete.")
        return deleted_ids

    def _save_results_to_jsonl(self, results, file_path):
        """API取得結果 (dictのリスト) をJSONLファイルに保存します。エラーのあるアイテムは除外します。

        Args:
            results (list[dict]): APIクライアントから返された結果のリスト。
            file_path (str): 保存先のJSONLファイルパス。

        Returns:
            bool: 実際にデータがファイルに書き込まれたかどうか。
        """
        count = 0
        error_count = 0
        logger.info(f"Attempting to save {len(results)} fetch results to {file_path}")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for item in results:
                    # itemがNoneや空でなく、かつ 'error' キーを含まないことを確認
                    if item and isinstance(item, dict) and "error" not in item:
                        try:
                            f.write(json.dumps(item, ensure_ascii=False) + "\n")
                            count += 1
                        except TypeError as e:
                             # JSONシリアライズできないデータ型が含まれている場合
                             logger.warning(f"Skipping item due to JSON serialization error: {e}. Item: {item.get('id', 'N/A')}")
                             error_count += 1
                    else:
                        # エラーが含まれるか、不正な形式のアイテム
                        title = item.get('title', 'N/A') if isinstance(item, dict) else 'N/A'
                        error_info = item.get('error', 'Invalid item format') if isinstance(item, dict) else 'Invalid item format'
                        logger.warning(f"Skipping item with error or invalid format: Title='{title}', Error='{error_info}'")
                        error_count += 1
            logger.info(f"Saved {count} valid items to {file_path}. Skipped {error_count} items due to errors or invalid format.")
            return count > 0 # 有効なデータが1件でも書き込まれたか
        except IOError as e:
            logger.error(f"Failed to write to JSONL file {file_path}: {e}", exc_info=True)
            return False # 書き込み失敗

    def apply_changes(self, update_results, insert_results):
        """取得した詳細情報を使ってデータベースを更新（削除、挿入、更新）します。"""
        logger.info("--- Starting to apply changes to the database ---")

        # 0. 一時JSONLファイルに結果を保存
        has_updates = self._save_results_to_jsonl(update_results, config.UPDATE_TEMP_FILE)
        has_inserts = self._save_results_to_jsonl(insert_results, config.INSERT_TEMP_FILE)

        # JSONLから読み込むためのカラム定義 (lines の構造はAPIレスポンスに依存)
        columns_def = """{
            'id': 'VARCHAR',
            'title': 'VARCHAR',
            'created': 'BIGINT',
            'updated': 'BIGINT',
            'lines': 'STRUCT(id VARCHAR, userId VARCHAR, "text" VARCHAR, created BIGINT, updated BIGINT)[]'
        }"""

        try:
            # DuckDBはデフォルトでトランザクショナルだが、明示的に開始しても良い
            # self.con.sql('BEGIN TRANSACTION')

            # 1. 削除処理
            deleted_ids = self.find_deleted_records_ids()
            if deleted_ids:
                # プレースホルダを使って安全に削除 (リストをタプルに変換)
                placeholders = ', '.join(['?'] * len(deleted_ids))
                sql_delete = f"DELETE FROM pages WHERE id IN ({placeholders})"
                delete_result = self._execute(sql_delete, deleted_ids, description="Deleting records")
                # fetchall()[0][0] はDELETE文では機能しないことがある。rowcountを使う方が確実な場合がある。
                deleted_count = delete_result.fetchone()
                logger.info(f"Deleted {deleted_count} records from 'pages' table.")
            else:
                logger.info("No records found to delete.")

            # 2. 挿入処理
            if has_inserts and os.path.exists(config.INSERT_TEMP_FILE):
                try:
                    self._create_table_from_jsonl('inserts', config.INSERT_TEMP_FILE, columns_def)
                    insert_sql = """
                        INSERT INTO pages (id, title, created, updated, lines)
                        SELECT id, title, created, updated, lines FROM inserts;
                    """
                    insert_result = self._execute(insert_sql, description="Inserting new records")
                    inserted_count = insert_result.fetchone()
                    logger.info(f"Inserted {inserted_count} new records into 'pages' table.")
                    self.con.execute("DROP TABLE inserts") # 一時テーブル削除
                except Exception as e:
                     logger.error(f"Failed during insertion process: {e}", exc_info=True)
                     # 挿入に失敗した場合、ロールバックするかどうか
                     # self.con.sql('ROLLBACK')
                     # raise
            elif has_inserts:
                 logger.warning(f"Insertion skipped because temporary file does not exist: {config.INSERT_TEMP_FILE}")
            else:
                 logger.info("No new records to insert.")


            # 3. 更新処理
            if has_updates and os.path.exists(config.UPDATE_TEMP_FILE):
                try:
                    self._create_table_from_jsonl('updates', config.UPDATE_TEMP_FILE, columns_def)
                    # DuckDBの UPDATE ... FROM 構文を使用
                    update_sql = """
                        UPDATE pages
                        SET title = u.title,
                            created = u.created,
                            updated = u.updated,
                            lines = u.lines
                        FROM updates AS u
                        WHERE pages.id = u.id;
                    """
                    update_result = self._execute(update_sql, description="Updating existing records")
                    updated_count = update_result.fetchone()
                    logger.info(f"Updated {updated_count} records in 'pages' table.")
                    self.con.execute("DROP TABLE updates") # 一時テーブル削除
                except Exception as e:
                     logger.error(f"Failed during update process: {e}", exc_info=True)
                     # 更新に失敗した場合
                     # self.con.sql('ROLLBACK')
                     # raise
            elif has_updates:
                 logger.warning(f"Update skipped because temporary file does not exist: {config.UPDATE_TEMP_FILE}")
            else:
                 logger.info("No records found to update.")

            # 成功した場合コミット (明示的にトランザクションを開始した場合)
            # self.con.sql('COMMIT')
            logger.info("--- Finished applying changes to the database ---")

        except Exception as e:
            logger.error(f"An error occurred while applying changes. Rolling back if transaction was started.", exc_info=True)
            # try:
            #     self.con.sql('ROLLBACK') # 明示的にトランザクションを開始した場合
            # except Exception as rb_e:
            #     logger.error(f"Failed to rollback transaction: {rb_e}")
            raise # エラーを呼び出し元に伝える

    def export_to_parquet(self, output_path):
        """現在の 'pages' テーブルの内容をParquetファイルにエクスポートします。"""
        if not self.con:
             logger.error("Cannot export to Parquet: Database connection is not available.")
             return

        logger.info(f"Exporting 'pages' table to Parquet file: {output_path}")
        try:
            # 出力先ディレクトリが存在するか確認
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                logger.info(f"Output directory '{output_dir}' does not exist. Creating it.")
                os.makedirs(output_dir, exist_ok=True)

            # COPY TO を使用してエクスポート
            export_sql = f"COPY pages TO '{output_path}' (FORMAT PARQUET)"
            self._execute(export_sql, description="Exporting table to Parquet")
            logger.info(f"Successfully exported 'pages' table to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export 'pages' table to Parquet file '{output_path}': {e}", exc_info=True)
            # エクスポート失敗は致命的ではないかもしれないので、ログに記録するだけにするか、エラーを再送出するか選択
            # raise

# --- デバッグ用: このファイルを直接実行した場合 (オプション) ---
# if __name__ == "__main__":
#     logger.info("Running database.py directly for testing...")
#     # テスト用のダミーファイルやデータを用意する必要がある
#     # 例:
#     # handler = DataHandler(':memory:')
#     # try:
#     #    # ダミーの pages.parquet や pages.jsonl を作成
#     #    # handler.load_initial_data()
#     #    # df_upd = handler.find_updated_records()
#     #    # print("Updates:", df_upd)
#     #    # # ... 他のメソッドのテスト ...
#     # finally:
#     #    handler.close()
#     pass
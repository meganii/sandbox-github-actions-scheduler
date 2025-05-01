# src/database.py の apply_changes メソッド内

    def apply_changes(self, update_results, insert_results):
        """取得した詳細情報を使ってデータベースを更新（削除、挿入、更新）します。"""
        logger.info("--- Starting to apply changes to the database ---")

        # ... (前半の JSONL 保存、接続チェック、カーソル取得などは同じ) ...
        if not self.con:
            logger.error("Cannot apply changes: Database connection is not available.")
            raise ConnectionError("Database connection is not available.")
        cur = self.con.cursor()

        try:
            # self.con.begin()

            # 1. 削除処理
            # ... (変更なし) ...
            deleted_ids = self.find_deleted_records_ids()
            if deleted_ids:
                placeholders = ', '.join(['?'] * len(deleted_ids))
                sql_delete = f"DELETE FROM pages WHERE id IN ({placeholders})"
                logger.debug(f"Executing DELETE: {sql_delete} | Params: {deleted_ids}")
                cur.execute(sql_delete, deleted_ids)
                deleted_count = cur.rowcount
                logger.info(f"Deleted {deleted_count} records from 'pages' table.")
            else:
                logger.info("No records found to delete.")


            # 2. 挿入処理
            # ... (変更なし) ...
            if has_inserts and os.path.exists(config.INSERT_TEMP_FILE):
                # ... (挿入処理、最後に DROP TABLE inserts) ...
                try:
                    self._create_table_from_jsonl('inserts', config.INSERT_TEMP_FILE, columns_def)
                    insert_sql = """
                        INSERT INTO pages (id, title, created, updated, lines)
                        SELECT id, title, created, updated, lines FROM inserts;
                    """
                    logger.debug(f"Executing INSERT: {insert_sql}")
                    cur.execute(insert_sql)
                    inserted_count = cur.rowcount
                    logger.info(f"Inserted {inserted_count} new records into 'pages' table.")
                    self.con.execute("DROP TABLE inserts")
                except Exception as e:
                     logger.error(f"Failed during insertion process: {e}", exc_info=True)

            elif has_inserts:
                 logger.warning(f"Insertion skipped because temporary file does not exist: {config.INSERT_TEMP_FILE}")
            else:
                 logger.info("No new records to insert.")


            # --- 3. 更新処理 (動的SET句) ---
            if has_updates and os.path.exists(config.UPDATE_TEMP_FILE):
                try:
                    # 一時テーブル 'updates' を作成
                    self._create_table_from_jsonl('updates', config.UPDATE_TEMP_FILE, columns_def)

                    # --- 動的に SET 句を生成 ---
                    logger.info("Dynamically generating UPDATE statement.")
                    # information_schemaから 'updates' テーブルのカラム名を取得
                    columns_query = """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'updates'
                        ORDER BY ordinal_position;
                    """
                    column_names_result = self.con.execute(columns_query).fetchall()

                    if not column_names_result:
                        raise RuntimeError("Could not retrieve column names for the 'updates' table to generate UPDATE statement.")

                    column_names = [row[0] for row in column_names_result]
                    logger.debug(f"Columns found in 'updates' table: {column_names}")

                    # 主キー (id) を除外した更新対象カラムリストを作成
                    update_columns = [col for col in column_names if col.lower() != 'id'] # 小文字で比較

                    if not update_columns:
                        logger.warning("No columns found to update in 'updates' table (excluding 'id'). Skipping UPDATE operation.")
                    else:
                        # SET句の各部分を作成 (例: "title" = u."title", "created" = u."created")
                        # カラム名にスペースや予約語が含まれる可能性を考慮し、ダブルクォートで囲む
                        set_clause_parts = [f'"{col}" = u."{col}"' for col in update_columns]
                        set_clause = ", ".join(set_clause_parts)

                        # 完全なUPDATE文を組み立て
                        update_sql = f"""
                            UPDATE pages
                            SET {set_clause}
                            FROM updates AS u
                            WHERE pages.id = u.id;
                        """
                        logger.debug(f"Executing dynamically generated UPDATE:\n{update_sql}")

                        # 動的に生成したUPDATE文を実行
                        cur.execute(update_sql)
                        updated_count = cur.rowcount
                        logger.info(f"Updated {updated_count} records in 'pages' table using dynamic SET clause.")
                    # --- 動的生成ここまで ---

                    # 一時テーブルを削除
                    self.con.execute("DROP TABLE updates")

                except Exception as e:
                     logger.error(f"Failed during dynamic update process: {e}", exc_info=True)
                     # self.con.rollback()
                     # raise
            elif has_updates:
                 logger.warning(f"Update skipped because temporary file does not exist: {config.UPDATE_TEMP_FILE}")
            else:
                 logger.info("No records found to update.")
            # --- 更新処理ここまで ---


            # self.con.commit()
            logger.info("--- Finished applying changes to the database ---")

        except Exception as e:
            logger.error(f"An error occurred while applying changes. Rolling back if transaction was started.", exc_info=True)
            # try:
            #     self.con.rollback()
            # except Exception as rb_e:
            #     logger.error(f"Failed to rollback transaction: {rb_e}")
            raise
        finally:
            # カーソルを閉じる
            cur.close()
            # 一時ファイルを削除
            # ... (変更なし) ...
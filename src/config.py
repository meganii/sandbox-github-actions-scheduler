# src/config.py
import os
from datetime import datetime
import logging # LOG_LEVEL 定義のために必要

# --- パス設定 ---
# このファイル (config.py) の場所を基準にプロジェクトルートを特定
# __file__ はこのスクリプトのパス -> os.path.dirname でディレクトリ取得 ->
# os.path.join で '..' を結合 -> os.path.abspath で絶対パスに
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# データディレクトリとログディレクトリのパスを定義
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')

# --- ディレクトリ自動作成 ---
# アプリケーション起動時に必要なディレクトリが存在するか確認し、なければ作成
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
except OSError as e:
    # ディレクトリ作成に失敗した場合のエラーハンドリング (ログ出力など)
    # ここでは単純に標準エラー出力に出力
    import sys
    print(f"Error creating directories: {e}", file=sys.stderr)
    # 必要に応じてプログラムを終了させるなどの処理を追加してもよい
    # sys.exit(1)

# --- CoSense プロジェクト設定 ---
# バックアップ対象の CoSense (旧 Scrapbox) プロジェクト名を指定
PROJECT = "meganii"

# --- ファイルパス定義 ---
# DATA_DIR を基準に各ファイルのパスを定義
PAGE_LIST_FILE = os.path.join(DATA_DIR, "pagelist.jsonl")  # 入力: 最新ページリスト (JSONL形式)
PAGES_DATA_FILE = os.path.join(DATA_DIR, 'pages.parquet') # 出力/DB代わり: 既存ページデータ (Parquet形式)
UPDATE_TEMP_FILE = os.path.join(DATA_DIR, 'update.jsonl')  # 一時: 更新対象ページの取得結果
INSERT_TEMP_FILE = os.path.join(DATA_DIR, 'insert.jsonl')  # 一時: 新規ページの取得結果
# STATS_FILE = os.path.join(DATA_DIR, "pages_stats.jsonl") # ページ統計情報ファイル (必要ならコメント解除)

# --- API クライアント設定 ---
CONCURRENCY_LIMIT = 10  # CoSense APIへの同時リクエスト数の上限

# --- ロギング設定 ---
# LOG_DIR を基準にログファイル名を定義
LOG_FILE_TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_FILE = os.path.join(LOG_DIR, f"cosense_backup_{LOG_FILE_TIMESTAMP}.log")

# ログレベル設定 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = logging.INFO

# ログフォーマット
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# --- データベース設定 (もしファイルDBを使う場合) ---
# DuckDB をメモリではなくファイルで使う場合のパス例
# DATABASE_PATH = os.path.join(DATA_DIR, 'cosense_backup.db')
DATABASE_PATH = ':memory:' # デフォルトはインメモリデータベース

# --- その他設定 (必要に応じて) ---
# 例: APIリトライ回数
# API_RETRY_COUNT = 3
# 例: APIリトライ遅延時間
# API_RETRY_DELAY = 1

# --- 設定値のバリデーション (オプション) ---
# 例えば PROJECT 名が空でないかチェックするなど
if not PROJECT:
    raise ValueError("PROJECT name in config.py cannot be empty.")

# --- デバッグ用: 設定値の表示 (オプション) ---
# if __name__ == "__main__":
#     # このファイルを直接実行したときに設定値を出力
#     print(f"PROJECT_ROOT: {PROJECT_ROOT}")
#     print(f"DATA_DIR: {DATA_DIR}")
#     print(f"LOG_DIR: {LOG_DIR}")
#     print(f"PROJECT: {PROJECT}")
#     print(f"PAGE_LIST_FILE: {PAGE_LIST_FILE}")
#     print(f"PAGES_DATA_FILE: {PAGES_DATA_FILE}")
#     print(f"LOG_FILE: {LOG_FILE}")
#     print(f"LOG_LEVEL: {LOG_LEVEL}")
#     print(f"DATABASE_PATH: {DATABASE_PATH}")
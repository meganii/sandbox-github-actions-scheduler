# src/logger_config.py
import logging
import sys
# 同じ src ディレクトリにある config モジュールをインポート
try:
    import config
except ImportError:
    # config.py が見つからない場合のエラー処理 (基本的なフォールバック)
    print("Error: config.py not found. Using default logging settings.", file=sys.stderr)
    # 最低限のデフォルト設定を定義
    class DefaultConfig:
        LOG_LEVEL = logging.INFO
        LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
        LOG_FILE = 'default_backup.log' # ルートディレクトリに作成される可能性
        PROJECT = 'default_project' # ロガー名で使用
    config = DefaultConfig()


def setup_logger(name="CosenseBackupTool"): # ロガーに固有の名前をつける
    """指定された設定に基づいてロガーをセットアップし、ロガーインスタンスを返します。

    Args:
        name (str, optional): ロガーの名前。デフォルトは "CosenseBackupTool"。

    Returns:
        logging.Logger: 設定済みのロガーインスタンス。
    """
    # config モジュールから設定値を取得
    log_level = getattr(config, 'LOG_LEVEL', logging.INFO) # getattrで安全に取得
    log_format = getattr(config, 'LOG_FORMAT', '%(asctime)s - %(levelname)s - %(message)s')
    log_file = getattr(config, 'LOG_FILE', 'fallback.log')

    # 指定された名前でロガーを取得
    logger = logging.getLogger(name)
    # logger.propagate = False # ルートロガーに伝播させない場合

    # すでにハンドラが設定されている場合は、重複追加を防ぐ
    if logger.hasHandlers():
        logger.handlers.clear()
        # logger.info("Cleared existing logger handlers.") # デバッグ用

    # ロガーのレベルを設定 (これより低いレベルのメッセージは無視される)
    logger.setLevel(log_level)

    # ログフォーマッターを作成
    formatter = logging.Formatter(log_format)

    # --- ファイルハンドラーの設定 ---
    try:
        # mode='a' で追記モード、encoding='utf-8' を指定
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        # ファイルハンドラーのレベルを設定 (ロガー本体のレベルと同じかそれ以上にできる)
        # file_handler.setLevel(logging.DEBUG) # 例: ファイルにはDEBUG以上を書き込む
        logger.addHandler(file_handler)
        # print(f"Logger setup: File handler added for {log_file}") # デバッグ用
    except PermissionError:
        print(f"Warning: Permission denied to write log file at {log_file}. Logging to file disabled.", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Failed to set up file handler for {log_file}: {e}. Logging to file disabled.", file=sys.stderr)

    # --- ストリームハンドラー（コンソール出力）の設定 ---
    stream_handler = logging.StreamHandler(sys.stdout) # 標準出力へ
    stream_handler.setFormatter(formatter)
    # ストリームハンドラーのレベルを設定 (例: コンソールには INFO 以上のみ表示)
    # stream_handler.setLevel(logging.INFO)
    logger.addHandler(stream_handler)
    # print("Logger setup: Stream handler added.") # デバッグ用

    # logger.info(f"Logger '{name}' configured with level {logging.getLevelName(log_level)}.") # 設定完了ログ
    return logger

# --- グローバルなロガーインスタンスを作成 ---
# モジュールがインポートされた時点で setup_logger が呼び出され、
# logger 変数にインスタンスが格納される。
# 他のモジュールからは `from logger_config import logger` で利用できる。
logger = setup_logger()

# --- モジュールインポート時の確認用ログ (オプション) ---
# logger.debug("logger_config module loaded and logger instance created.")

# --- デバッグ用: このファイルを直接実行した場合の動作確認 (オプション) ---
# if __name__ == "__main__":
#     print(f"Running logger_config.py directly for testing...")
#     print(f"Log level set to: {logging.getLevelName(logger.level)}")
#     print(f"Log file path: {config.LOG_FILE if hasattr(config, 'LOG_FILE') else 'N/A'}")
#
#     logger.debug("This is a debug message.")
#     logger.info("This is an info message.")
#     logger.warning("This is a warning message.")
#     logger.error("This is an error message.")
#     logger.critical("This is a critical message.")
#
#     try:
#         1 / 0
#     except ZeroDivisionError:
#         logger.exception("Caught an exception!")
#
#     print("Check the console output and the log file (if configured correctly).")
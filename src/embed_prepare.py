import duckdb
from logger_config import setup_logger

DATA_URL = "https://github.com/meganii/sandbox-github-actions-scheduler/releases/latest/download/pages.parquet"

logger = setup_logger(__name__)


def main():
    logger.info("Starting prepare step: expanding parquet into lines table")
    con = duckdb.connect("data/lines.duckdb")
    
    sql = f"""
    CREATE TABLE lines (
        page_id VARCHAR,
        title VARCHAR,
        first_line_id VARCHAR,
        block_text VARCHAR,
        updated BIGINT
    );

    -- 一時テーブルに展開
    CREATE TEMP TABLE expanded_lines AS
    SELECT 
        t.id              AS page_id,
        t.title,
        t.created,
        u.ord             AS line_no,
        l.created         AS line_created,
        l.id              AS line_id,
        l.text,
        l.updated         AS line_updated,
        l.userId          AS line_userId
    FROM read_parquet('{DATA_URL}') t
    CROSS JOIN UNNEST(t.lines) WITH ORDINALITY AS u(l, ord);

    WITH
    line_blocks AS (
        SELECT
        *,
        SUM(CASE WHEN "text" = '' THEN 1 ELSE 0 END) OVER (
            PARTITION BY
            page_id
            ORDER BY
            line_no
        ) AS block_id
        FROM
        expanded_lines
    ),
    target_blocks AS (
        SELECT DISTINCT
            page_id,
            block_id
        FROM
            line_blocks
    ),
    -- 元のgrouped_text_blockを、よりシンプルな形に変更
    block_contents AS (
        SELECT
            lb.page_id,
            lb.title,
            lb.block_id, -- 集約のキーとして利用
            lb.line_no,
            lb.line_id,
            lb."text",
            lb.line_updated AS updated
        FROM
            line_blocks AS lb
            INNER JOIN target_blocks AS tb ON lb.page_id = tb.page_id
            AND lb.block_id = tb.block_id
        WHERE
            lb."text" != ''
    )

    -- 最終的なSELECT文で、ブロックごとに集約
    INSERT INTO lines
        SELECT
            page_id,
            title,
            -- 各ブロックの先頭行のline_idを取得
            arg_min(line_id, line_no) AS first_line_id,
            -- ブロック内のテキストを改行で連結
            string_agg("text", '\n' ORDER BY line_no) AS block_text,
            max(updated) AS updated
        FROM
            block_contents
        GROUP BY
            page_id,
            title,
            block_id
        ORDER BY
            max(updated) DESC,
            page_id;
    
    """
    try:
        logger.debug("Executing SQL to build lines table from %s", DATA_URL)
        result = con.execute(sql)
        con.commit()
        logger.info("Prepared lines table successfully")
        logger.debug("Execute result: %s", result)
    except Exception:
        logger.exception("Failed to prepare lines table")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()

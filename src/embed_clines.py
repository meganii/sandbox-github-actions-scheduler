import duckdb
from sentence_transformers import SentenceTransformer
from logger_config import setup_logger
import os

logger = setup_logger(__name__)


def main():
    logger.info("Starting embedding pipeline")
    con = duckdb.connect("data/lines.duckdb")
    try:
        logger.debug("Installing and loading DuckDB extensions")
        con.install_extension("vss")
        con.load_extension("vss")
        con.install_extension("fts")
        con.load_extension("fts")

        logger.debug("Preparing clines table")
        con.sql("""
        DROP TABLE IF EXISTS clines;
        DROP SEQUENCE IF EXISTS id_sequence;
        """)

        con.sql("""
        CREATE SEQUENCE id_sequence START 1;
        CREATE TABLE IF NOT EXISTS clines (
            id INTEGER DEFAULT nextval('id_sequence') PRIMARY KEY,
            page_id VARCHAR,
            title VARCHAR,
            text VARCHAR,
            updated BIGINT,
            embedding FLOAT[1024]
        );
        """)

        logger.info("Fetching rows from lines table")
        df = con.sql("""
        SELECT * FROM lines;
        """).fetchdf()

        model_name = "hotchpotch/static-embedding-japanese"
        logger.info("Loading SentenceTransformer model %s", model_name)
        model = SentenceTransformer(model_name, device="cpu")

        total = len(df)
        logger.info("Encoding %d rows", total)
        # # テストで、10件だけ処理する
        # for index, row in df.head(10).iterrows():
        for index, row in df.iterrows():
            try:
                logger.info("Encoding row %d/%d: page_id=%s", index + 1, total, row['page_id'])
                embedding = model.encode(row['block_text'], show_progress_bar=False)
                con.execute("""
                    INSERT INTO clines (page_id, title, text, updated, embedding)
                    VALUES (?, ?, ?, ?, ?)
                """, (row['page_id'], row['title'], row['block_text'], row['updated'], embedding.tolist()))
            except Exception as e:
                logger.exception("Failed to process row %s: %s", index, e)

        con.commit()
        logger.info("Committed embeddings to database")
        # Export clines table to Parquet
        out_path = os.environ.get("CLINES_OUTPUT", "data/clines.parquet")
        try:
            logger.info("Exporting clines table to %s", out_path)
            # Use DuckDB's COPY TO for efficient Parquet export
            con.execute(f"COPY clines TO '{out_path}' (FORMAT PARQUET)")
            logger.info("Exported clines to %s", out_path)
        except Exception:
            logger.exception("Failed to export clines to Parquet %s", out_path)
            raise
    except Exception:
        logger.exception("Embedding pipeline failed")
        raise
    finally:
        con.close()
        logger.info("Closed database connection")


if __name__ == "__main__":
    main()
"""
scripts/manual_scrape.py
Standalone script to run the scraping pipeline manually.
Usage: python scripts/manual_scrape.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from loguru import logger
logger.add("logs/manual_scrape.log", rotation="5 MB")

from scraper.pipeline import ScrapingPipeline
from backend.core.database import SessionLocal


def main():
    logger.info("=== Manual Scrape Started ===")
    db = SessionLocal()
    try:
        pipeline = ScrapingPipeline(db_session=db)
        result = pipeline.run_incremental()
        print("\n" + "=" * 50)
        print("SCRAPING SUMMARY")
        print("=" * 50)
        for k, v in result.items():
            print(f"  {k}: {v}")
        print("=" * 50)
    except Exception as e:
        logger.error(f"Manual scrape failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

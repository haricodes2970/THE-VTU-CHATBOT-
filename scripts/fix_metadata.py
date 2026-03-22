"""
scripts/fix_metadata.py
Re-runs metadata extraction on all existing DB circulars
and updates both PostgreSQL and Pinecone vector metadata.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import defaultdict
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from scraper.vtu_scraper import VTUScraper


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    scraper = VTUScraper.__new__(VTUScraper)

    circulars = db.execute(text("SELECT id, title, scheme, semester_range, exam_session FROM circulars")).fetchall()
    logger.info(f"Found {len(circulars)} circulars to fix")

    fixed = 0
    unknown_session = 0
    schemes = defaultdict(int)
    semesters = defaultdict(int)

    for c in circulars:
        title = c.title or ""
        new_scheme = scraper.detect_scheme(title)
        new_sem = scraper.extract_semester_range(title)
        new_session = scraper.extract_exam_session(title)

        db.execute(
            text("UPDATE circulars SET scheme=:scheme, semester_range=:sem, exam_session=:session, is_indexed=false WHERE id=:id"),
            {"scheme": new_scheme, "sem": new_sem, "session": new_session, "id": c.id}
        )

        schemes[new_scheme] += 1
        semesters[new_sem] += 1
        if new_session == "UnknownSession":
            unknown_session += 1
            logger.warning(f"Still UnknownSession: [{c.id}] {title!r}")
        fixed += 1

    db.commit()
    db.close()

    logger.info(f"Fixed {fixed} circulars")
    logger.info(f"Still UnknownSession: {unknown_session}")
    logger.info(f"Schemes: {dict(schemes)}")
    logger.info(f"Semesters: {dict(semesters)}")


if __name__ == "__main__":
    main()

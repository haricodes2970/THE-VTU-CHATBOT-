"""
scripts/reindex_circulars.py
Re-embeds ALL circulars in the database into Pinecone.
Useful when changing the embedding model or chunk strategy.
Usage: python scripts/reindex_circulars.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from loguru import logger
from sqlalchemy import select

from backend.core.database import SessionLocal
from backend.models.models import Circular
from backend.rag_pipeline.rag_chain import RAGChain


def main():
    db = SessionLocal()
    try:
        # Reset is_indexed flag so all circulars are reprocessed
        all_circulars = db.execute(select(Circular)).scalars().all()
        total = len(all_circulars)
        logger.info(f"Found {total} circulars to reindex")

        for circ in all_circulars:
            circ.is_indexed = False
        db.commit()

        # Re-embed all
        rag = RAGChain()
        result = rag.index_all_pending(db)

        print("\n" + "=" * 50)
        print("REINDEX SUMMARY")
        print("=" * 50)
        print(f"  Total circulars: {result['total']}")
        print(f"  Successfully indexed: {result['indexed']}")
        print(f"  Failed: {result['failed']}")
        print("=" * 50)

    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    confirm = input(f"This will re-embed all circulars into Pinecone. Continue? (yes/no): ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        sys.exit(0)
    main()

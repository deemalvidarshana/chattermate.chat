"""CLI for converting legacy full-page knowledge rows to bounded chunks.

Usage:
    python -m app.knowledge.rechunk_existing --organization <uuid>
    python -m app.knowledge.rechunk_existing --organization <uuid> --source https://example.com
"""

from __future__ import annotations

import argparse
from uuid import UUID

from app.database import SessionLocal
from app.knowledge.page_editor import rechunk_source
from app.models.knowledge import Knowledge


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", required=True, type=UUID)
    parser.add_argument("--source")
    parser.add_argument(
        "--page",
        help="Only reprocess this exact grouped page id (requires --source)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess sources that already carry chunk metadata",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        query = db.query(Knowledge).filter(Knowledge.organization_id == args.organization)
        if args.source:
            query = query.filter(Knowledge.source == args.source)
        sources = query.order_by(Knowledge.id.asc()).all()
        seen = set()
        totals = {"sources": 0, "pages": 0, "chunks": 0}
        for knowledge in sources:
            # Duplicate relational rows for the same org/source share the same
            # vector rows. Process that physical source only once.
            key = (knowledge.schema, knowledge.table_name, knowledge.source)
            if key in seen:
                continue
            seen.add(key)
            result = rechunk_source(
                db,
                knowledge,
                force=args.force,
                page_id=args.page,
            )
            totals["sources"] += 1
            totals["pages"] += result["pages_rechunked"]
            totals["chunks"] += result["chunks_written"]
            print(
                f"{knowledge.source}: {result['pages_rechunked']} page(s), "
                f"{result['chunks_written']} chunk(s)"
            )
        print(
            f"Complete: {totals['sources']} source(s), {totals['pages']} page(s), "
            f"{totals['chunks']} chunk(s)"
        )


if __name__ == "__main__":
    main()

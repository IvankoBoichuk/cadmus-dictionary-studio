"""One-off CLI: enqueue page splitting for dictionaries verified before it existed.

Run via ``make backfill-pages``. Safe to re-run: it also re-enqueues any
source file whose previous split attempt failed, since the underlying query
excludes only ``completed`` splits.
"""

import cadmus.infrastructure.identity  # noqa: F401 -- registers `users` for FKs
from cadmus.config import Settings
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.source_pages_queue import CeleryPagesQueue
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.sources import SourcePagesQueue, SourcesUnitOfWorkFactory

from cadmus_worker.celery_app import celery_app


def _enqueue_pending(
    unit_of_work_factory: SourcesUnitOfWorkFactory, queue: SourcePagesQueue
) -> int:
    with unit_of_work_factory() as unit_of_work:
        source_files = unit_of_work.sources.list_source_files_pending_page_split()
    for source_file in source_files:
        queue.enqueue_split(source_file.id)
    return len(source_files)


def main() -> None:
    settings = Settings()
    engine = create_database_engine(settings)
    unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    queue = CeleryPagesQueue(celery_app)

    enqueued = _enqueue_pending(unit_of_work_factory, queue)
    print(f"enqueued page splitting for {enqueued} dictionary source file(s)")


if __name__ == "__main__":
    main()

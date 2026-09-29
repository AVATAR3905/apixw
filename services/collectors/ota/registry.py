"""Registry mapping a `sources.name` DB value to its OTA scraper class.

This is the mechanism that lets a *new, permitted* source be added without
editing `CollectionScheduler` or `MultiSourceFlightOrchestrator` (PRD US-014:
"connector interfaces to be standardized so that new sources can be added
without rewriting the core system"). Onboarding a new source becomes:

    1. Write a `BaseOTAScraper` subclass implementing `_execute_scrape` and
       `_generate_calibrated_quotes` (see CONTRIBUTING.md).
    2. Decorate it with `@register_ota_scraper("<exact sources.name value>")`.
    3. Add/approve its row in the `sources` table.

No other file needs to change. Compliance is enforced the same way it always
was: `get_approved_ota_scrapers` only returns scrapers whose DB row currently
passes `SourceRegistryService.can_collect` (PRD §4.4/§12 -- a source with
unresolved permission status must not be automatically enabled).
"""

import logging
from typing import Dict, List, Type

from sqlalchemy.orm import Session

from packages.schemas.models import Source
from services.collectors.ota.base_ota_scraper import BaseOTAScraper
from services.collectors.source_registry import SourceRegistryService

logger = logging.getLogger(__name__)

_OTA_SCRAPER_REGISTRY: Dict[str, Type[BaseOTAScraper]] = {}


def register_ota_scraper(source_name: str):
    """Class decorator registering a `BaseOTAScraper` subclass under the exact
    `sources.name` value it corresponds to."""

    def _decorator(cls: Type[BaseOTAScraper]) -> Type[BaseOTAScraper]:
        _OTA_SCRAPER_REGISTRY[source_name] = cls
        return cls

    return _decorator


def get_registered_ota_scrapers() -> Dict[str, Type[BaseOTAScraper]]:
    """All registered scraper classes, keyed by `sources.name`, regardless of
    their current DB approval state."""
    return dict(_OTA_SCRAPER_REGISTRY)


def get_approved_ota_scrapers(db: Session) -> List[BaseOTAScraper]:
    """Instantiates every registered scraper whose `sources` row is currently
    approved+enabled (`SourceRegistryService.can_collect`). A registered
    scraper with no matching DB row, or a DB row that isn't yet approved, is
    silently skipped -- writing the scraper class does not itself turn on
    live collection against that site.
    """
    if not _OTA_SCRAPER_REGISTRY:
        return []

    sources_by_name = {
        s.name: s
        for s in db.query(Source).filter(Source.name.in_(_OTA_SCRAPER_REGISTRY.keys())).all()
    }

    scrapers: List[BaseOTAScraper] = []
    for source_name, scraper_cls in _OTA_SCRAPER_REGISTRY.items():
        source = sources_by_name.get(source_name)
        if source is None:
            logger.warning(
                "OTA scraper %r is registered but has no matching row in `sources`; skipping.",
                source_name,
            )
            continue
        if not SourceRegistryService.can_collect(source):
            continue
        scrapers.append(scraper_cls())

    return scrapers

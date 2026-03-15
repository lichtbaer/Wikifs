"""Backend clients."""

from wikifs.backends.wikidata import WikidataClient, WikidataError
from wikifs.backends.wikidata_models import (
    Claim,
    ClaimValue,
    ClassMembers,
    RelationTarget,
    ResolvedEntity,
    ResolveResult,
    SearchResult,
    WikidataEntity,
)
from wikifs.backends.wikipedia import WikipediaClient, WikipediaError, WikipediaNotFoundError
from wikifs.backends.wikipedia_models import (
    ArticleContent,
    ArticleSummary,
    Section,
)

__all__ = [
    "WikidataClient",
    "WikidataError",
    "WikipediaClient",
    "WikipediaError",
    "WikipediaNotFoundError",
    "Claim",
    "ClaimValue",
    "ClassMembers",
    "RelationTarget",
    "ResolveResult",
    "ResolvedEntity",
    "SearchResult",
    "WikidataEntity",
    "ArticleContent",
    "ArticleSummary",
    "Section",
]

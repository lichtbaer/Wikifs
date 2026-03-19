"""Rewrite virtual paths (e.g. Wikidata Q-IDs) before routing."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wikifs.backends.wikidata import WikidataClient
    from wikifs.tracing import TraceContext

# /wiki/entities/Q12345/... or /wiki/entities/Q12345 (root entity path)
_ENTITY_QID_PATTERN = re.compile(
    r"^(/wiki/entities/)(Q[1-9][0-9]*)(/.*)?$",
    re.IGNORECASE,
)


def rewrite_entity_qid_path(
    path: str,
    wikidata: WikidataClient,
    lang: str,
    ctx: TraceContext,
) -> str:
    """Replace Q-ID segment with Wikipedia title (underscore form) when resolvable."""
    m = _ENTITY_QID_PATTERN.match(path)
    if not m:
        return path
    prefix, qid, suffix = m.group(1), m.group(2).upper(), m.group(3) or ""
    with ctx.phase("resolve_qid_path"):
        resolved = wikidata.resolve_entity_by_id(qid, lang=lang, ctx=ctx)
    if resolved is None or not resolved.wikipedia_title:
        return path
    wiki_seg = resolved.wikipedia_title.replace(" ", "_")
    return f"{prefix}{wiki_seg}{suffix}"

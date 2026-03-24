"""Wikidata API client — Entity resolution, claims, relations, SPARQL."""

from __future__ import annotations

import hashlib
import json
import re
import time
from contextlib import nullcontext
from typing import Any, cast
from urllib.parse import quote

import requests

from wikifs.backends.utils import record_api_error as _record_api_error
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
from wikifs.cache import Cache
from wikifs.config import ApiConfig
from wikifs.errors import ErrorCollector
from wikifs.tracing import TraceContext


class WikidataError(Exception):
    """Base exception for Wikidata client errors."""

    pass


class WikidataRateLimitError(WikidataError):
    """HTTP 429 Rate Limit exceeded."""

    pass


class WikidataTimeoutError(WikidataError):
    """Request timeout."""

    pass


def _sparql_cache_key(query: str) -> str:
    """Generate cache key for SPARQL query."""
    h = hashlib.sha256(query.encode()).hexdigest()
    return f"wikidata:sparql:{h}"


def _resolve_cache_key(name: str, lang: str) -> str:
    """Generate cache key for entity resolution."""
    return f"wikidata:resolve:{name}:{lang}"


def _entity_cache_key(entity_id: str) -> str:
    """Generate cache key for entity data."""
    return f"wikidata:entity:{entity_id}"


def _search_cache_key(query: str, lang: str, limit: int) -> str:
    """Generate cache key for search results."""
    return f"wikidata:search:{query}:{lang}:{limit}"


def _property_labels_cache_key(prop_ids: str, lang: str) -> str:
    """Generate cache key for property labels."""
    return f"wikidata:property_labels:{prop_ids}:{lang}"


_WIKIDATA_ID_RE = re.compile(r"^Q\d+$")
_LETTER_RE = re.compile(r"^[A-Z]$")


def _validate_wikidata_id(qid: str) -> str:
    """Validate and return a Wikidata entity ID (e.g. Q64)."""
    if not _WIKIDATA_ID_RE.match(qid):
        raise WikidataError(f"Invalid Wikidata ID: {qid!r}")
    return qid


def _validate_letter(letter: str) -> str:
    """Validate a single uppercase letter for SPARQL FILTER."""
    if not _LETTER_RE.match(letter):
        raise WikidataError(f"Invalid letter filter: {letter!r}")
    return letter


def _resolve_sitelink_title(sitelinks: dict[str, str], lang: str = "de") -> str:
    """Pick the best Wikipedia title from sitelinks, preferring the requested language."""
    preferred = f"{lang}wiki"
    fallback = "enwiki" if lang != "en" else "dewiki"
    return (
        sitelinks.get(preferred)
        or sitelinks.get(fallback, "")
        or (next(iter(sitelinks.values()), "") if sitelinks else "")
    )


def _http_get(
    url: str,
    config: ApiConfig,
    ctx: TraceContext | None = None,
    error_collector: ErrorCollector | None = None,
) -> bytes:
    """Perform HTTP GET with retry logic for 429 and 5xx."""
    headers = {"User-Agent": config.user_agent}
    timeout = config.request_timeout_seconds

    last_exc: Exception | None = None
    for attempt in range(4):  # 1 initial + 3 retries for 429
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
        except requests.Timeout as e:
            _record_api_error(
                error_collector,
                ctx,
                "timeout",
                "error",
                f"Request timeout: {url}",
                {"url": url, "error": str(e)},
            )
            raise WikidataTimeoutError(f"Request timeout: {url}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "60")
            try:
                wait_sec = int(retry_after)
            except ValueError:
                wait_sec = 60
            if attempt < 3:
                time.sleep(wait_sec)
                continue
            _record_api_error(
                error_collector,
                ctx,
                "api",
                "error",
                f"Rate limit exceeded after 3 retries: {url}",
                {"url": url, "status_code": 429},
            )
            raise WikidataRateLimitError(
                f"Rate limit exceeded after 3 retries: {url}"
            ) from None

        if resp.status_code == 404:
            _record_api_error(
                error_collector,
                ctx,
                "api",
                "warning",
                f"Not found: {url}",
                {"url": url, "status_code": 404},
            )
            raise WikidataError("Not found") from None

        if 500 <= resp.status_code < 600:
            if attempt == 0:
                time.sleep(1)
                continue
            _record_api_error(
                error_collector,
                ctx,
                "api",
                "critical",
                f"Server error {resp.status_code}: {url}",
                {"url": url, "status_code": resp.status_code},
            )
            raise WikidataError(f"Server error {resp.status_code}: {url}") from None

        if resp.status_code != 200:
            _record_api_error(
                error_collector,
                ctx,
                "api",
                "error",
                f"HTTP {resp.status_code}: {url}",
                {"url": url, "status_code": resp.status_code},
            )
            raise WikidataError(f"HTTP {resp.status_code}: {url}") from None

        data: bytes = resp.content
        if ctx is not None:
            ctx.record_api_call(url, len(data))
        return data

    raise WikidataError(f"Request failed: {url}") from last_exc


def _fetch_or_cache(
    cache: Cache,
    key: str,
    url: str,
    config: ApiConfig,
    ctx: TraceContext | None,
    error_collector: ErrorCollector | None = None,
) -> bytes | None:
    """Fetch from cache or API. Returns None on 404."""
    cached = cache.get(key, ctx)
    if cached is not None:
        return cached
    try:
        data = _http_get(url, config, ctx, error_collector)
        cache.set(key, data)
        return data
    except WikidataError as e:
        if "Not found" in str(e):
            return None
        raise


def _parse_entity_from_search(item: dict[str, Any], lang: str) -> SearchResult:
    """Parse search result item to SearchResult."""
    entity_id = item.get("id", "")
    label = item.get("label", "")
    description = item.get("description", "")

    # wbsearchentities does not return sitelinks; use label as wikipedia_title
    wikipedia_title: str | None = label.replace(" ", "_") if label else None

    return SearchResult(
        entity_id=entity_id,
        label=label,
        description=description,
        wikipedia_title=wikipedia_title,
    )


def _parse_entity_data(
    raw: dict[str, Any], entity_id: str, lang: str = "de"
) -> WikidataEntity:
    """Parse EntityData JSON to WikidataEntity."""
    entities = raw.get("entities", {})
    ent = entities.get(entity_id)
    if not ent:
        raise WikidataError(f"Entity {entity_id} not in response")

    labels = ent.get("labels", {})
    label = ""
    if lang in labels:
        label = labels[lang].get("value", "")

    descriptions = ent.get("descriptions", {})
    description = ""
    if lang in descriptions:
        description = descriptions[lang].get("value", "")

    aliases_list: list[str] = []
    aliases_obj = ent.get("aliases", {}).get(lang, [])
    for a in aliases_obj:
        if isinstance(a, dict) and "value" in a:
            aliases_list.append(a["value"])

    sitelinks_out: dict[str, str] = {}
    sitelinks = ent.get("sitelinks", {})
    for site, data in sitelinks.items():
        if isinstance(data, dict) and "title" in data:
            sitelinks_out[site] = data["title"]

    claims_raw = ent.get("claims", {})
    claims: list[Claim] = []
    # We need property labels - they come from the entity or we fetch separately
    # For now, use property_id as label if we don't have it
    for prop_id, claim_list in claims_raw.items():
        for c in claim_list:
            if not isinstance(c, dict):
                continue
            mainsnak = c.get("mainsnak", {})
            if mainsnak.get("snaktype") == "novalue":
                continue
            datavalue = mainsnak.get("datavalue", {})
            val_type = datavalue.get("type", "unknown")
            value = _format_claim_value(datavalue)
            qualifiers: dict[str, str] = {}
            for qid, qlist in c.get("qualifiers", {}).items():
                for q in qlist:
                    if isinstance(q, dict) and "datavalue" in q:
                        qualifiers[qid] = _format_claim_value(q["datavalue"])
            rank = c.get("rank", "normal")
            claims.append(
                Claim(
                    property_id=prop_id,
                    property_label=prop_id,
                    value=value,
                    value_type=val_type,
                    qualifiers=qualifiers,
                    rank=rank,
                )
            )

    last_modified = ent.get("lastrevid", "")

    return WikidataEntity(
        entity_id=entity_id,
        label=label,
        description=description,
        aliases=aliases_list,
        claims=claims,
        sitelinks=sitelinks_out,
        last_modified=str(last_modified),
    )


def _format_claim_value(datavalue: dict[str, Any]) -> str:
    """Format datavalue to string."""
    if not datavalue:
        return ""
    val_type = datavalue.get("type", "")
    value = datavalue.get("value")
    if value is None:
        return ""
    if val_type == "string":
        return str(value)
    if val_type == "wikibase-entityid":
        return str(value.get("id", ""))
    if val_type == "quantity":
        amount = str(value.get("amount", "0"))
        return amount.replace("+", "").split("/")[0]
    if val_type == "time":
        return str(value.get("time", ""))
    if val_type == "globecoordinate":
        lat = value.get("latitude", 0)
        lon = value.get("longitude", 0)
        return f"{lat},{lon}"
    return str(value)


def _resolve_entity_from_search(
    item: dict[str, Any], lang: str
) -> ResolvedEntity | None:
    """Build ResolvedEntity from search result if we have enough data."""
    entity_id = item.get("id", "")
    if not entity_id:
        return None
    label = item.get("label", "")
    description = item.get("description", "")

    aliases_list: list[str] = []
    for a in item.get("aliases", []):
        if isinstance(a, dict) and "value" in a:
            aliases_list.append(a["value"])
        elif isinstance(a, str):
            aliases_list.append(a)

    wikipedia_title = ""
    if "sitelinks" in item:
        sl = item["sitelinks"]
        if isinstance(sl, dict):
            for site, data in sl.items():
                if isinstance(data, dict) and "title" in data:
                    wikipedia_title = data["title"]
                    break
    if not wikipedia_title:
        wikipedia_title = label.replace(" ", "_")

    return ResolvedEntity(
        entity_id=entity_id,
        label=label,
        description=description,
        wikipedia_title=wikipedia_title,
        aliases=aliases_list,
    )


class WikidataClient:
    """Wikidata API client with caching and trace integration."""

    def __init__(
        self,
        config: ApiConfig,
        cache: Cache,
        error_collector: ErrorCollector | None = None,
    ) -> None:
        self._config = config
        self._cache = cache
        self._error_collector = error_collector
        self._base = config.wikidata_base_url.rstrip("/")

    def resolve_entity(
        self,
        name: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> ResolveResult:
        """Resolve entity by name. Returns ResolveResult with entity or suggestions."""
        key = _resolve_cache_key(name, lang)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            data = json.loads(cached)
            entity_dict = data.get("entity")
            cached_entity: ResolvedEntity | None = (
                ResolvedEntity(
                    entity_id=entity_dict["entity_id"],
                    label=entity_dict["label"],
                    description=entity_dict["description"],
                    wikipedia_title=entity_dict["wikipedia_title"],
                    aliases=entity_dict.get("aliases", []),
                )
                if entity_dict
                else None
            )
            return ResolveResult(
                entity=cached_entity,
                suggestions=data.get("suggestions", []),
            )

        # Search with spaces (Wikidata labels use spaces, not underscores)
        search_term = name.replace("_", " ")
        url = (
            f"{self._base}/w/api.php"
            f"?action=wbsearchentities"
            f"&search={quote(search_term)}"
            f"&language={lang}"
            f"&format=json"
            f"&limit=10"
        )

        cm = ctx.phase("resolve_entity") if ctx else nullcontext()
        with cm:
            data_bytes = _http_get(url, self._config, ctx, self._error_collector)

        data = json.loads(data_bytes)
        search_results = data.get("search", [])

        # Match: prefer label match; when multiple, prefer city/Stadt/Metropole
        search_normalized = name.replace("_", " ").lower()
        entity: ResolvedEntity | None = None
        suggestions: list[str] = []
        exact_matches: list[ResolvedEntity] = []
        all_results: list[ResolvedEntity] = []

        for item in search_results:
            res = _resolve_entity_from_search(item, lang)
            if res is None:
                continue
            all_results.append(res)
            label_norm = res.label.replace("_", " ").lower()
            wiki_norm = res.wikipedia_title.replace("_", " ").lower()
            if label_norm == search_normalized or wiki_norm == search_normalized:
                exact_matches.append(res)
            else:
                suggestions.append(res.wikipedia_title)

        # For "X am Main" pattern (e.g. Frankfurt am Main), prefer city over station/ship
        prefer_city = " am " in search_normalized or "_am_" in name.lower()
        if prefer_city:
            for res in all_results:
                d = res.description.lower()
                if "stadt" in d or "metropole" in d or "city" in d:
                    entity = res
                    suggestions = []  # Clear when we have entity
                    break

        if entity is None and exact_matches:
            for res in exact_matches:
                d = res.description.lower()
                if "stadt" in d or "metropole" in d or "city" in d:
                    entity = res
                    break
            if entity is None:
                entity = exact_matches[0]
        elif entity is None and search_results:
            for item in search_results[:5]:
                res = _resolve_entity_from_search(item, lang)
                if res:
                    suggestions.append(res.wikipedia_title)

        to_cache = json.dumps({
            "entity": {
                "entity_id": entity.entity_id,
                "label": entity.label,
                "description": entity.description,
                "wikipedia_title": entity.wikipedia_title,
                "aliases": entity.aliases,
            } if entity else None,
            "suggestions": suggestions,
        }).encode()
        self._cache.set(key, to_cache)

        return ResolveResult(entity=entity, suggestions=suggestions)

    def resolve_entity_by_id(
        self,
        entity_id: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> ResolvedEntity | None:
        """Resolve entity by Wikidata ID (e.g. Q1794)."""
        entity_data = self.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity_data is None:
            return None
        wiki_title = _resolve_sitelink_title(entity_data.sitelinks, lang)
        return ResolvedEntity(
            entity_id=entity_data.entity_id,
            label=entity_data.label,
            description=entity_data.description,
            wikipedia_title=wiki_title,
            aliases=entity_data.aliases,
        )

    def get_entity(
        self,
        entity_id: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> WikidataEntity | None:
        """Fetch full entity data from EntityData JSON."""
        key = _entity_cache_key(entity_id)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            raw = json.loads(cached)
            return _parse_entity_data(raw, entity_id, lang)

        url = f"{self._base}/wiki/Special:EntityData/{entity_id}.json"
        data = _fetch_or_cache(
            self._cache, key, url, self._config, ctx, self._error_collector
        )
        if data is None:
            return None
        return _parse_entity_data(json.loads(data), entity_id, lang)

    def get_claims(
        self,
        entity_id: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> list[Claim]:
        """Get all claims for entity. Returns empty list if not found."""
        entity = self.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return []
        return entity.claims

    def get_claim_value(
        self,
        entity_id: str,
        property_id: str,
        ctx: TraceContext | None = None,
    ) -> ClaimValue | None:
        """Get formatted claim value for property. Returns None if not found."""
        claims = self.get_claims(entity_id, ctx=ctx)
        for c in claims:
            if c.property_id == property_id:
                qual_str = ", ".join(c.qualifiers.values()) if c.qualifiers else ""
                formatted = f"{c.value}"
                if qual_str:
                    formatted = f"{c.value} ({qual_str})"
                return ClaimValue(
                    value=c.value,
                    formatted=formatted,
                    qualifiers=c.qualifiers,
                    value_type=c.value_type,
                )
        return None

    def get_relation_targets(
        self,
        entity_id: str,
        property_id: str,
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> list[RelationTarget]:
        """Get relation targets for property (e.g. P131 -> Hessen, Deutschland)."""
        entity = self.get_entity(entity_id, lang=lang, ctx=ctx)
        if entity is None:
            return []
        targets: list[RelationTarget] = []
        for c in entity.claims:
            if c.property_id != property_id:
                continue
            # Value is entity ID for entity-type claims
            target_id = c.value
            if target_id.startswith("Q"):
                target_entity = self.get_entity(target_id, lang=lang, ctx=ctx)
                if target_entity:
                    wiki_title = _resolve_sitelink_title(target_entity.sitelinks, lang)
                    targets.append(
                        RelationTarget(
                            entity_id=target_id,
                            label=target_entity.label,
                            wikipedia_title=wiki_title,
                        )
                    )
        return targets

    def get_property_labels(
        self,
        prop_ids: list[str],
        lang: str = "de",
        ctx: TraceContext | None = None,
    ) -> dict[str, str]:
        """Fetch labels for properties. Returns {prop_id: label}."""
        if not prop_ids:
            return {}
        ids_str = "|".join(sorted(prop_ids))
        key = _property_labels_cache_key(ids_str, lang)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            return cast(dict[str, str], json.loads(cached))

        url = (
            f"{self._base}/w/api.php"
            f"?action=wbgetentities"
            f"&ids={quote(ids_str, safe='|')}"
            f"&props=labels"
            f"&languages={lang}"
            f"&format=json"
        )
        data_bytes = _http_get(url, self._config, ctx, self._error_collector)
        data = json.loads(data_bytes)
        entities = data.get("entities", {})
        result: dict[str, str] = {}
        for pid in prop_ids:
            ent = entities.get(pid)
            if ent and isinstance(ent, dict):
                labels = ent.get("labels", {})
                if lang in labels and isinstance(labels[lang], dict):
                    result[pid] = labels[lang].get("value", pid)
                else:
                    result[pid] = pid
            else:
                result[pid] = pid
        self._cache.set(key, json.dumps(result).encode())
        return result

    def search_entities(
        self,
        query: str,
        lang: str = "de",
        limit: int = 10,
        ctx: TraceContext | None = None,
    ) -> list[SearchResult]:
        """Search entities via wbsearchentities."""
        key = _search_cache_key(query, lang, limit)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            data = json.loads(cached)
            return [SearchResult(**r) for r in data]

        url = (
            f"{self._base}/w/api.php"
            f"?action=wbsearchentities"
            f"&search={quote(query)}"
            f"&language={lang}"
            f"&format=json"
            f"&limit={limit}"
        )
        data_bytes = _fetch_or_cache(
            self._cache, key, url, self._config, ctx, self._error_collector
        )
        if data_bytes is None:
            return []
        data = json.loads(data_bytes)
        results = [
            _parse_entity_from_search(item, lang)
            for item in data.get("search", [])
        ]
        to_cache = json.dumps([
            {
                "entity_id": r.entity_id,
                "label": r.label,
                "description": r.description,
                "wikipedia_title": r.wikipedia_title,
            }
            for r in results
        ]).encode()
        self._cache.set(key, to_cache)
        return results

    def sparql_query(
        self,
        query: str,
        ctx: TraceContext | None = None,
    ) -> list[dict[str, Any]]:
        """Execute SPARQL query. Returns list of bindings."""
        key = _sparql_cache_key(query)
        cached = self._cache.get(key, ctx)
        if cached is not None:
            return cast(list[dict[str, Any]], json.loads(cached))

        url = (
            f"https://query.wikidata.org/sparql"
            f"?query={quote(query)}"
            f"&format=json"
        )
        data_bytes = _http_get(url, self._config, ctx, self._error_collector)
        data = json.loads(data_bytes)
        results = data.get("results", {}).get("bindings", [])
        # Normalize: extract values from bindings
        out: list[dict[str, Any]] = []
        for b in results:
            row: dict[str, Any] = {}
            for k, v in b.items():
                if isinstance(v, dict) and "value" in v:
                    row[k] = v["value"]
                else:
                    row[k] = v
            out.append(row)
        self._cache.set(key, json.dumps(out).encode())
        return out

    def get_class_members(
        self,
        class_id: str,
        limit: int = 100,
        offset: int = 0,
        ctx: TraceContext | None = None,
    ) -> ClassMembers:
        """Get class members via SPARQL (P31 -> class_id)."""
        if not class_id.startswith("Q"):
            class_id = f"Q{class_id}"
        class_id = _validate_wikidata_id(class_id)
        query = (
            f"SELECT ?x WHERE {{ ?x wdt:P31 wd:{class_id} }} "
            f"LIMIT {limit + 1} OFFSET {offset}"
        )
        bindings = self.sparql_query(query, ctx)
        has_more = len(bindings) > limit
        bindings = bindings[:limit]

        members: list[SearchResult] = []
        for b in bindings:
            x = b.get("x", "")
            if isinstance(x, str) and x.startswith("http"):
                entity_id = x.split("/")[-1]
            else:
                entity_id = str(x)
            if entity_id:
                entity = self.get_entity(entity_id, ctx=ctx)
                if entity:
                    wiki_title = _resolve_sitelink_title(entity.sitelinks)
                    members.append(
                        SearchResult(
                            entity_id=entity_id,
                            label=entity.label,
                            description=entity.description,
                            wikipedia_title=wiki_title or None,
                        )
                    )
                else:
                    members.append(
                        SearchResult(
                            entity_id=entity_id,
                            label=entity_id,
                            description="",
                            wikipedia_title=None,
                        )
                    )

        return ClassMembers(
            members=members,
            total_count=None,
            has_more=has_more,
        )

    def get_class_members_by_label_range(
        self,
        class_id: str,
        start_letter: str,
        end_letter: str,
        limit: int = 500,
        ctx: TraceContext | None = None,
    ) -> list[SearchResult]:
        """Get class members whose label starts with A-end_letter (for segment listing)."""
        if not class_id.startswith("Q"):
            class_id = f"Q{class_id}"
        class_id = _validate_wikidata_id(class_id)
        start_letter = _validate_letter(start_letter.upper())
        end_letter = _validate_letter(end_letter.upper())
        query = (
            "SELECT ?x ?label WHERE {"
            f" ?x wdt:P31 wd:{class_id} ."
            " ?x rdfs:label ?label ."
            " FILTER(LANG(?label) = 'de')"
            f" FILTER(UCASE(SUBSTR(?label, 1, 1)) >= '{start_letter}' "
            f"   && UCASE(SUBSTR(?label, 1, 1)) <= '{end_letter}')"
            f" }} LIMIT {limit}"
        )
        bindings = self.sparql_query(query, ctx)
        members: list[SearchResult] = []
        for b in bindings:
            x = b.get("x", "")
            if isinstance(x, str) and x.startswith("http"):
                entity_id = x.split("/")[-1]
            else:
                entity_id = str(x)
            if entity_id:
                entity = self.get_entity(entity_id, ctx=ctx)
                if entity:
                    wiki_title = _resolve_sitelink_title(entity.sitelinks)
                    members.append(
                        SearchResult(
                            entity_id=entity_id,
                            label=entity.label,
                            description=entity.description,
                            wikipedia_title=wiki_title or None,
                        )
                    )
        return members



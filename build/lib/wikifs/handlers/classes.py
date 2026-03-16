"""Classes handler — list classes, list class members with pagination."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikipedia import WikipediaClient
from wikifs.formatter import format_directory_listing, format_error
from wikifs.models import HandlerConfig, HandlerResponse

if TYPE_CHECKING:
    from wikifs.tracing import TraceContext

# Phase 1: hardcoded classes (city, country, river, person, university, company)
CLASSES: dict[str, str] = {
    "city": "Q515",
    "country": "Q6256",
    "river": "Q4022",
    "person": "Q5",
    "university": "Q3918",
    "company": "Q7836",
}


class ClassesHandler:
    """Handler for class navigation."""

    def __init__(
        self,
        wikidata: WikidataClient,
        wikipedia: WikipediaClient,
        config: HandlerConfig,
    ) -> None:
        self._wikidata = wikidata
        self._wikipedia = wikipedia
        self._config = config

    def handle(
        self,
        command: str,
        params: dict[str, str],
        flags: list[str],
        pattern: str | None,
        route: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle classes requests."""
        if route == "classes.list_classes":
            return self._handle_list_classes()
        if route == "classes.list_class_members":
            class_name = params.get("class", "")
            return self._handle_list_members(class_name, ctx)
        if route == "classes.list_class_segment":
            class_name = params.get("class", "")
            segment = params.get("segment", "")
            return self._handle_list_segment(class_name, segment, ctx)
        return HandlerResponse(
            output=format_error(f"Unknown route: {route}", "invalid_command"),
            exit_code=1,
            error_type="invalid_command",
        )

    def _handle_list_classes(self) -> HandlerResponse:
        """Handle ls /wiki/classes/."""
        entries = [(f"{k}/", v) for k, v in CLASSES.items()]
        output = format_directory_listing(entries, detailed=True)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_list_members(
        self,
        class_name: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle ls /wiki/classes/{class}/."""
        class_id = CLASSES.get(class_name.lower())
        if class_id is None:
            return HandlerResponse(
                output=format_error(f"Unknown class: {class_name}", "not_found"),
                exit_code=2,
                error_type="not_found",
            )
        limit = self._config.pagination_default_limit
        members = self._wikidata.get_class_members(
            class_id, limit=limit + 1, offset=0, ctx=ctx
        )
        if len(members.members) <= self._config.pagination_default_limit:
            entries = [
                (m.wikipedia_title or m.label.replace(" ", "_") or m.entity_id, None)
                for m in members.members
            ]
            output = format_directory_listing(entries, detailed=False)
            return HandlerResponse(output=output, exit_code=0)
        segments = ["A-D/", "E-H/", "I-L/", "M-P/", "Q-T/", "U-Z/"]
        entries = [(s, None) for s in segments]
        output = format_directory_listing(entries, detailed=False)
        return HandlerResponse(output=output, exit_code=0)

    def _handle_list_segment(
        self,
        class_name: str,
        segment: str,
        ctx: TraceContext,
    ) -> HandlerResponse:
        """Handle ls /wiki/classes/{class}/{segment}/."""
        class_id = CLASSES.get(class_name.lower())
        if class_id is None:
            return HandlerResponse(
                output=format_error(f"Unknown class: {class_name}", "not_found"),
                exit_code=2,
                error_type="not_found",
            )
        segment_clean = segment.rstrip("/").upper()
        seg_map = {
            "A-D": ("A", "D"),
            "E-H": ("E", "H"),
            "I-L": ("I", "L"),
            "M-P": ("M", "P"),
            "Q-T": ("Q", "T"),
            "U-Z": ("U", "Z"),
        }
        if segment_clean not in seg_map:
            return HandlerResponse(
                output=format_error(f"Unknown segment: {segment}", "not_found"),
                exit_code=2,
                error_type="not_found",
            )
        start_letter, end_letter = seg_map[segment_clean]
        limit = self._config.pagination_max_limit
        members = self._wikidata.get_class_members_by_label_range(
            class_id, start_letter, end_letter, limit=limit, ctx=ctx
        )
        titles = [
            m.wikipedia_title or m.label.replace(" ", "_") or m.entity_id
            for m in members
        ]
        entries = [(f"{t}/", None) for t in sorted(set(titles)) if t]
        output = format_directory_listing(entries, detailed=False)
        return HandlerResponse(output=output, exit_code=0)

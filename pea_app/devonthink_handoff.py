from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_DEVONTHINK_MCP = Path(
    "/Applications/DEVONthink.app/Contents/Library/LoginItems/"
    "DEVONthink MCP.app/Contents/MacOS/DEVONthink MCP"
)
WRITABLE_DATABASES = ("Inbox",)
RESTRICTED_DATABASE = "Restricted"


class DevonThinkError(RuntimeError):
    pass


class DevonThinkSecurityError(DevonThinkError):
    pass


class DevonThinkDuplicateError(DevonThinkError):
    pass


class ToolSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


SessionFactory = Callable[[], Any]


@dataclass(frozen=True)
class DevonThinkHandoff:
    markdown: str
    title: str
    source_reference: str
    source_url: str
    content_fingerprint: str
    target_database: str = "Inbox"
    destination: str = ""
    record_kind: str = "minutes"
    status: str = "awaiting_duplicate_check"


@dataclass(frozen=True)
class ImportReview:
    handoff: DevonThinkHandoff
    database_uuid: str
    database_name: str
    source_matches: tuple[dict[str, Any], ...]
    title_matches: tuple[dict[str, Any], ...]

    @property
    def is_clear(self) -> bool:
        return not self.source_matches and not self.title_matches

    @property
    def target_description(self) -> str:
        location = self.handoff.destination or "Database inbox"
        return f"{self.database_name} · {location}"


@dataclass(frozen=True)
class ImportReceipt:
    uuid: str
    name: str
    database_name: str
    location: str
    item_url: str
    content_verified: bool


@dataclass(frozen=True)
class DevonThinkMinutesSource:
    uuid: str
    title: str
    added_date: str
    markdown: str

    @property
    def source_reference(self) -> str:
        return f"devonthink:{self.uuid}"


def format_duplicate_review_message(review: ImportReview) -> str:
    source_count = len(review.source_matches)
    title_count = len(review.title_matches)
    reasons: list[str] = []
    if source_count:
        noun = "record" if source_count == 1 else "records"
        reasons.append(
            f"DEVONthink already contains {source_count} {noun} with the same source reference"
        )
    if title_count:
        noun = "document" if title_count == 1 else "documents"
        reasons.append(f"DEVONthink already contains {title_count} {noun} with the same title")

    reason = " and ".join(reasons) or "the duplicate check was not clear"
    if review.handoff.record_kind == "daily-summary":
        guidance = "Review or merge the existing daily summary separately."
    elif review.handoff.record_kind == "weekly-summary":
        guidance = "Review or merge the existing weekly summary separately."
    elif review.handoff.record_kind == "remarkable-note":
        guidance = (
            "Review the existing reMarkable import in DEVONthink before filing this source again."
        )
    else:
        guidance = (
            "If the records cover the same meeting, merge the new minutes with the existing "
            "record. If they cover different meetings, amend the title to include the meeting "
            "date and review the import again."
        )
    return (
        f"No record was written because {reason}.\n\n"
        f"Source-reference matches: {source_count}\n"
        f"Title matches: {title_count}\n\n"
        f"{guidance}"
    )


def prepare_handoff(
    markdown: str,
    source_reference: str,
    target_database: str = "Inbox",
    destination: str = "",
    record_kind: str = "minutes",
) -> DevonThinkHandoff:
    cleaned_markdown = markdown.strip()
    cleaned_reference = source_reference.strip()
    cleaned_database = target_database.strip()
    cleaned_destination = destination.strip()
    cleaned_kind = record_kind.strip()
    if not cleaned_markdown:
        raise ValueError("Markdown content is required before a handoff can be prepared.")
    if not cleaned_reference:
        raise ValueError("A source reference is required for duplicate protection.")
    if cleaned_database.casefold() == RESTRICTED_DATABASE.casefold():
        raise DevonThinkSecurityError("Restricted databases are not authorised AI destinations.")
    if cleaned_database not in WRITABLE_DATABASES:
        raise DevonThinkSecurityError("The selected DEVONthink database is not authorised.")
    if cleaned_kind not in {"minutes", "daily-summary", "weekly-summary", "remarkable-note"}:
        raise DevonThinkSecurityError("The DEVONthink record type is not authorised.")

    title = _markdown_title(cleaned_markdown)
    digest_material = f"{cleaned_reference}\n{cleaned_markdown}".encode()
    fingerprint = hashlib.sha256(digest_material).hexdigest()
    return DevonThinkHandoff(
        markdown=cleaned_markdown + "\n",
        title=title,
        source_reference=cleaned_reference,
        source_url=f"pea-source://{quote(cleaned_reference, safe='')}",
        content_fingerprint=fingerprint,
        target_database=cleaned_database,
        destination=cleaned_destination,
        record_kind=cleaned_kind,
    )


def prepare_remarkable_handoff(
    title: str,
    markdown: str,
    source_reference: str,
) -> DevonThinkHandoff:
    cleaned_title = " ".join(title.split()).lstrip("#").strip()
    if not cleaned_title:
        raise ValueError("A reMarkable document title is required.")
    body = markdown.strip()
    if not body:
        raise ValueError("Existing reMarkable text is required before import review.")
    return prepare_handoff(
        f"# {cleaned_title}\n\n{body}",
        source_reference,
        target_database="Inbox",
        record_kind="remarkable-note",
    )


class DevonThinkService:
    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        self._session_factory = session_factory or open_devonthink_session

    def review(self, handoff: DevonThinkHandoff) -> ImportReview:
        return anyio.run(self._review, handoff)

    def import_record(self, handoff: DevonThinkHandoff) -> ImportReceipt:
        return anyio.run(self._import_record, handoff)

    def load_minutes(self, start_date: str, end_date: str, database: str = "Inbox") -> list[DevonThinkMinutesSource]:
        """Load reviewed Minutes added in [start_date, end_date) from one authorised database."""
        return anyio.run(self._load_minutes, start_date, end_date, database)

    async def _load_minutes(
        self, start_date: str, end_date: str, database: str
    ) -> list[DevonThinkMinutesSource]:
        if database.casefold() == RESTRICTED_DATABASE.casefold() or database not in WRITABLE_DATABASES:
            raise DevonThinkSecurityError("The selected DEVONthink database is not authorised.")
        async with self._session_factory() as session:
            databases = _as_list(await _call_json(session, "get_databases", {}))
            visible_names = {str(item.get("name", "")) for item in databases}
            if RESTRICTED_DATABASE in visible_names:
                raise DevonThinkSecurityError(
                    "Security check failed: the restricted database is visible through DEVONthink MCP."
                )
            target = next((item for item in databases if item.get("name") == database), None)
            if target is None or not target.get("uuid"):
                raise DevonThinkError(f"DEVONthink database '{database}' is not available.")
            database_uuid = str(target["uuid"])
            query = f"tags:minutes added>={start_date} added<{end_date}"
            result = await _call_json(
                session,
                "search_records",
                {
                    "database_uuid": database_uuid,
                    "query": query,
                    "limit": 100,
                    "sort": "added",
                    "fields": ["uuid", "name", "tags", "additionDate"],
                },
            )
            hits = _search_results(result)
            if len(hits) >= 100:
                raise DevonThinkError(
                    "The selected period contains at least 100 Minutes records; narrow the period."
                )
            sources: list[DevonThinkMinutesSource] = []
            for hit in hits:
                tags = {str(tag).casefold() for tag in hit.get("tags", [])}
                uuid = str(hit.get("uuid", ""))
                if not uuid or "minutes" not in tags or "pea-import" not in tags:
                    continue
                markdown = await _call_text(
                    session,
                    "get_record_text",
                    {"database_uuid": database_uuid, "uuid": uuid},
                )
                if markdown.strip():
                    sources.append(
                        DevonThinkMinutesSource(
                            uuid=uuid,
                            title=str(hit.get("name") or "Meeting Minutes"),
                            added_date=str(hit.get("additionDate") or ""),
                            markdown=markdown,
                        )
                    )
            return sources

    async def _review(self, handoff: DevonThinkHandoff) -> ImportReview:
        async with self._session_factory() as session:
            return await self._review_with_session(session, handoff)

    async def _review_with_session(
        self,
        session: ToolSession,
        handoff: DevonThinkHandoff,
    ) -> ImportReview:
        databases = _as_list(await _call_json(session, "get_databases", {}))
        visible_names = {str(item.get("name", "")) for item in databases}
        if RESTRICTED_DATABASE in visible_names:
            raise DevonThinkSecurityError(
                "Security check failed: the restricted database is visible through DEVONthink MCP."
            )
        database = next(
            (item for item in databases if item.get("name") == handoff.target_database),
            None,
        )
        if database is None:
            raise DevonThinkError(
                f"DEVONthink database '{handoff.target_database}' is not available."
            )
        database_uuid = str(database.get("uuid", ""))
        if not database_uuid:
            raise DevonThinkError("DEVONthink returned a database without a UUID.")

        source_result = await _call_json(
            session,
            "lookup_records",
            {"database_uuid": database_uuid, "url": handoff.source_url},
        )
        title_result = await _call_json(
            session,
            "lookup_records",
            {"database_uuid": database_uuid, "name": handoff.title},
        )
        return ImportReview(
            handoff=handoff,
            database_uuid=database_uuid,
            database_name=str(database["name"]),
            source_matches=tuple(_lookup_results(source_result)),
            title_matches=tuple(_lookup_results(title_result)),
        )

    async def _import_record(self, handoff: DevonThinkHandoff) -> ImportReceipt:
        async with self._session_factory() as session:
            review = await self._review_with_session(session, handoff)
            if not review.is_clear:
                raise DevonThinkDuplicateError(_duplicate_message(review))

            arguments: dict[str, Any] = {
                "database_uuid": review.database_uuid,
                "name": handoff.title,
                "type": "markdown",
                "content": handoff.markdown,
                "comment": _record_comment(handoff),
                "url": handoff.source_url,
            }
            if handoff.record_kind != "remarkable-note":
                arguments["tags"] = [handoff.record_kind, "pea-import"]
            if handoff.destination:
                arguments["destination"] = handoff.destination

            created = await _call_json(session, "create_record", arguments)
            record = _record_dict(created)
            uuid = str(record.get("uuid", ""))
            if not uuid:
                raise DevonThinkError("DEVONthink created no verifiable record UUID.")

            properties = _record_dict(
                await _call_json(
                    session,
                    "get_record_properties",
                    {"database_uuid": review.database_uuid, "uuid": uuid},
                )
            )
            text = await _call_text(
                session,
                "get_record_text",
                {"database_uuid": review.database_uuid, "uuid": uuid},
            )
            content_verified = text.strip() == handoff.markdown.strip()
            if str(properties.get("name", "")) != handoff.title or not content_verified:
                raise DevonThinkError(
                    "The record was created, but post-write verification did not match. "
                    f"Review x-devonthink-item://{uuid} manually."
                )

            location = str(properties.get("location") or record.get("location") or "")
            return ImportReceipt(
                uuid=uuid,
                name=handoff.title,
                database_name=review.database_name,
                location=location,
                item_url=f"x-devonthink-item://{uuid}",
                content_verified=True,
            )


@asynccontextmanager
async def open_devonthink_session() -> AsyncIterator[ClientSession]:
    if not DEFAULT_DEVONTHINK_MCP.is_file():
        raise DevonThinkError("The DEVONthink MCP executable is not installed.")
    parameters = StdioServerParameters(command=str(DEFAULT_DEVONTHINK_MCP), args=["--stdio"])
    try:
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            yield session
    except Exception as exc:
        if error := _find_devonthink_error(exc):
            raise error
        raise DevonThinkError("The DEVONthink MCP connection failed.") from exc


async def _call_json(session: ToolSession, name: str, arguments: dict[str, Any]) -> Any:
    result = await session.call_tool(name, arguments)
    if getattr(result, "isError", False):
        raise DevonThinkError(f"DEVONthink MCP tool '{name}' failed.")
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise DevonThinkError(
                    f"DEVONthink MCP tool '{name}' returned invalid data."
                ) from exc
    raise DevonThinkError(f"DEVONthink MCP tool '{name}' returned no data.")


async def _call_text(session: ToolSession, name: str, arguments: dict[str, Any]) -> str:
    result = await session.call_tool(name, arguments)
    if getattr(result, "isError", False):
        raise DevonThinkError(f"DEVONthink MCP tool '{name}' failed.")
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return _record_text(structured)
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if isinstance(text, str):
            return text
    raise DevonThinkError(f"DEVONthink MCP tool '{name}' returned no text.")


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    if isinstance(value, dict) and isinstance(value.get("databases"), list):
        return value["databases"]
    raise DevonThinkError("DEVONthink returned an unexpected database list.")


def _lookup_results(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return [item for item in value["results"] if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise DevonThinkError("DEVONthink returned an unexpected duplicate-check result.")


def _search_results(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return [item for item in value["results"] if isinstance(item, dict)]
    raise DevonThinkError("DEVONthink returned an unexpected search result.")


def _record_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if isinstance(value.get("record"), dict):
            return value["record"]
        return value
    raise DevonThinkError("DEVONthink returned unexpected record metadata.")


def _record_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content"):
            if isinstance(value.get(key), str):
                return value[key]
    raise DevonThinkError("DEVONthink returned no verifiable record content.")


def _find_devonthink_error(exc: BaseException) -> DevonThinkError | None:
    if isinstance(exc, DevonThinkError):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for nested in exc.exceptions:
            if error := _find_devonthink_error(nested):
                return error
    return None


def _markdown_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    raise ValueError("Markdown content must start with a level-one title.")


def _record_comment(handoff: DevonThinkHandoff) -> str:
    return (
        f"PEA source: {handoff.source_reference}\n"
        f"PEA SHA-256: {handoff.content_fingerprint}"
    )


def _duplicate_message(review: ImportReview) -> str:
    if review.source_matches:
        return "A DEVONthink record already uses this source reference. No record was created."
    return "A DEVONthink record with this title already exists. No record was created."

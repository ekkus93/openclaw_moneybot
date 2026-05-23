"""Unit tests for the arXiv research plugin."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

import openclaw_moneybot.plugins.arxiv_research_plugin.service as arxiv_service
from openclaw_moneybot.plugins.arxiv_research_plugin import (
    ArxivPaperRequest,
    ArxivResearchPlugin,
    ArxivResearchPluginError,
    ArxivSearchRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, ArxivResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService

_SEARCH_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>arXiv Query: all:"graph neural networks"</title>
  <id>https://arxiv.org/api/q1</id>
  <updated>2026-05-21T00:00:00Z</updated>
  <opensearch:totalResults>42</opensearch:totalResults>
  <entry>
    <id>https://arxiv.org/abs/2401.01234v2</id>
    <updated>2026-05-20T12:00:00Z</updated>
    <published>2024-01-03T12:00:00Z</published>
    <title>  Graph Neural Networks for Bounded Agents  </title>
    <summary>
      This paper studies graph neural networks under bounded execution
      and governance constraints.
    </summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Grace Hopper</name></author>
    <link rel="alternate" type="text/html" href="https://arxiv.org/abs/2401.01234v2" />
    <link title="pdf" rel="related" type="application/pdf"
          href="https://arxiv.org/pdf/2401.01234v2.pdf" />
    <arxiv:primary_category term="cs.LG" />
    <category term="cs.LG" />
    <category term="cs.AI" />
    <arxiv:comment>Accepted at ExampleConf</arxiv:comment>
    <arxiv:doi>10.1000/example-doi</arxiv:doi>
  </entry>
</feed>
"""

_PAPER_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>arXiv Query: id_list=2401.01234v2</title>
  <id>https://arxiv.org/api/q2</id>
  <updated>2026-05-21T00:00:00Z</updated>
  <opensearch:totalResults>1</opensearch:totalResults>
  <entry>
    <id>https://arxiv.org/abs/2401.01234v2</id>
    <updated>2026-05-20T12:00:00Z</updated>
    <published>2024-01-03T12:00:00Z</published>
    <title>Graph Neural Networks for Bounded Agents</title>
    <summary>""" + ("Abstract body " * 30) + """</summary>
    <author><name>Ada Lovelace</name></author>
    <link rel="alternate" type="text/html" href="https://arxiv.org/abs/2401.01234v2" />
    <link title="pdf" rel="related" type="application/pdf"
          href="https://arxiv.org/pdf/2401.01234v2.pdf" />
    <arxiv:primary_category term="cs.LG" />
  </entry>
</feed>
"""


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    handler: httpx.BaseTransport | None = None,
) -> tuple[ArxivResearchPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = ArxivResearchPlugin(
        ArxivResearchConfig(enabled=enabled, max_results=5, max_summary_chars=120),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def audit_event_payloads(ledger_service: LedgerService) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for event in ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT):
        payload = event.payload.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def test_search_returns_bounded_normalized_results(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == (
            "https://export.arxiv.org/api/query"
            "?search_query=all%3A%22graph+neural+networks%22&start=2&max_results=1"
            "&sortBy=relevance&sortOrder=descending"
        )
        return httpx.Response(
            200,
            text=_SEARCH_FEED,
            headers={"Content-Type": "application/atom+xml"},
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.search(ArxivSearchRequest(query="graph neural networks", count=1, start=2))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.ARXIV_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.query == "graph neural networks"
    assert result.start == 2
    assert result.result_count == 1
    assert result.total_results == 42
    assert result.results[0].arxiv_id == "2401.01234v2"
    assert result.results[0].authors == ["Ada Lovelace", "Grace Hopper"]
    assert result.results[0].primary_category == "cs.LG"
    assert evidence[0].evidence_type == "arxiv_search_response"


def test_arxiv_request_models_normalize_and_validate_ids() -> None:
    request = ArxivPaperRequest(arxiv_id=" 2401.01234v2 ")

    assert request.arxiv_id == "2401.01234v2"

    with pytest.raises(ValueError, match="at least 1 character|must not be empty"):
        ArxivPaperRequest(arxiv_id=" ")


def test_get_paper_returns_bounded_paper_metadata(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["id_list"] == "2401.01234v2"
        return httpx.Response(
            200,
            text=_PAPER_FEED,
            headers={"Content-Type": "application/atom+xml"},
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_paper(ArxivPaperRequest(arxiv_id="2401.01234v2"))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.ARXIV_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.arxiv_id == "2401.01234v2"
    assert result.paper.title == "Graph Neural Networks for Bounded Agents"
    assert len(result.paper.summary) == 120
    assert result.paper.primary_category == "cs.LG"
    assert str(result.paper.pdf_url) == "https://arxiv.org/pdf/2401.01234v2.pdf"
    assert evidence[0].evidence_type == "arxiv_paper_response"


def test_search_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.search(ArxivSearchRequest(query="graph neural networks"))


def test_get_paper_rejects_malformed_payloads(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<feed xmlns='http://www.w3.org/2005/Atom'><entry><id>https://arxiv.org/abs/1</id></entry></feed>",
            headers={"Content-Type": "application/atom+xml"},
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(ArxivResearchPluginError, match="missing arXiv entry title"):
        plugin.get_paper(ArxivPaperRequest(arxiv_id="1"))


def test_search_surfaces_transport_failures_as_plugin_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(ArxivResearchPluginError, match="unavailable"):
        plugin.search(ArxivSearchRequest(query="graph neural networks"))


def test_search_and_lookup_enforce_limits_and_record_failures(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    with pytest.raises(ValueError, match="configured maximum"):
        plugin.search(ArxivSearchRequest(query="graph neural networks", count=6))

    def missing_paper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<feed xmlns='http://www.w3.org/2005/Atom'></feed>",
            headers={"Content-Type": "application/atom+xml"},
        )

    lookup_plugin, ledger_service = make_plugin(
        tmp_path / "lookup",
        handler=httpx.MockTransport(missing_paper_handler),
    )
    with pytest.raises(ArxivResearchPluginError, match="no matching paper"):
        lookup_plugin.get_paper(ArxivPaperRequest(arxiv_id="2401.01234v2"))
    assert audit_event_payloads(ledger_service)[-1]["event_name"] == "arxiv_paper_not_found"


def test_parse_feed_and_helpers_cover_xml_root_totals_and_required_fields(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ArxivResearchPluginError, match="valid Atom XML"):
        plugin._parse_feed("<not-xml")
    with pytest.raises(ArxivResearchPluginError, match="Atom feed"):
        plugin._parse_feed("<root />")

    entries, total = plugin._parse_feed(
        """
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
          <opensearch:totalResults>not-a-number</opensearch:totalResults>
        </feed>
        """
    )
    assert entries == []
    assert total is None

    entry = ET.fromstring(
        """
        <entry xmlns="http://www.w3.org/2005/Atom"
               xmlns:arxiv="http://arxiv.org/schemas/atom">
          <id>https://arxiv.org/abs/2401.01234v2</id>
          <updated>2026-05-20T12:00:00Z</updated>
          <published>2024-01-03T12:00:00Z</published>
          <title>Graph Paper</title>
          <summary>Summary text</summary>
          <author><name>First Author</name></author>
          <author><name>Second Author</name></author>
          <link rel="alternate" type="text/html" href="https://arxiv.org/abs/2401.01234v2" />
          <link rel="related"
                type="application/pdf"
                href="https://arxiv.org/pdf/2401.01234v2.pdf" />
          <link title="pdf"
                rel="alternate"
                type="text/html"
                href="https://arxiv.org/pdf/by-title.pdf" />
          <arxiv:comment>  Accepted  </arxiv:comment>
        </entry>
        """
    )
    parsed_entry = plugin._parse_entry(entry)
    assert parsed_entry.authors == ["First Author", "Second Author"]
    assert str(parsed_entry.pdf_url) == "https://arxiv.org/pdf/2401.01234v2.pdf"
    assert parsed_entry.comment == "Accepted"

    with pytest.raises(ArxivResearchPluginError, match="missing arXiv entry title"):
        plugin._parse_entry(
            ET.fromstring(
                """
                <entry xmlns="http://www.w3.org/2005/Atom"
                       xmlns:arxiv="http://arxiv.org/schemas/atom">
                  <id>https://arxiv.org/abs/2401.01234v2</id>
                  <updated>2026-05-20T12:00:00Z</updated>
                  <published>2024-01-03T12:00:00Z</published>
                  <summary>Summary text</summary>
                </entry>
                """
            )
        )

    empty_entry = ET.fromstring('<entry xmlns="http://www.w3.org/2005/Atom"></entry>')
    with pytest.raises(ArxivResearchPluginError, match="missing test description"):
        arxiv_service.ArxivResearchPlugin._required_text(
            empty_entry,
            "atom:title",
            "test description",
        )
    assert arxiv_service.ArxivResearchPlugin._optional_text(empty_entry, "atom:title") is None
    assert (
        arxiv_service.ArxivResearchPlugin._clean_text("  many   spaces here ")
        == "many spaces here"
    )
    assert arxiv_service.ArxivResearchPlugin._search_query('graph "agents"') == 'all:"graph agents"'
    assert arxiv_service.ArxivResearchPlugin._api_sort_by("lastupdateddate") == "lastUpdatedDate"
    assert arxiv_service.ArxivResearchPlugin._api_sort_by("submitteddate") == "submittedDate"
    assert arxiv_service.ArxivResearchPlugin._api_sort_by("other") == "relevance"


def test_get_paper_records_transport_failure(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(ArxivResearchPluginError, match="unavailable"):
        plugin.get_paper(ArxivPaperRequest(arxiv_id="2401.01234v2"))

    assert audit_event_payloads(ledger_service)[-1]["event_name"] == "arxiv_paper_lookup_failed"

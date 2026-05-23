"""Unit tests for the biomedical research plugin."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.biomedical_research_plugin import (
    BiomedicalPaperRequest,
    BiomedicalResearchPlugin,
    BiomedicalResearchPluginError,
    BiomedicalSearchRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, BiomedicalResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService

_PUBMED_FETCH_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2024</Year>
              <Month>05</Month>
              <Day>01</Day>
            </PubDate>
          </JournalIssue>
          <Title>Example Journal</Title>
        </Journal>
        <ArticleTitle>Bounded biomedical agents</ArticleTitle>
        <Abstract>
          <AbstractText Label="Background">Agents help with discovery.</AbstractText>
          <AbstractText>They stay bounded and auditable.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <LastName>Lovelace</LastName>
            <ForeName>Ada</ForeName>
          </Author>
          <Author>
            <CollectiveName>Research Team</CollectiveName>
          </Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1000/biomed</ArticleId>
        <ArticleId IdType="pmc">PMC12345</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    handler: httpx.BaseTransport | None = None,
) -> tuple[BiomedicalResearchPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = BiomedicalResearchPlugin(
        BiomedicalResearchConfig(enabled=enabled, max_results=5, max_abstract_chars=80),
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


def test_pubmed_search_returns_bounded_normalized_results(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/esearch.fcgi"):
            assert request.url.params["db"] == "pubmed"
            assert request.url.params["term"] == "cancer biomarkers AND 2024[pdat]"
            assert request.url.params["retmax"] == "1"
            assert request.url.params["retstart"] == "1"
            return httpx.Response(
                200,
                json={"esearchresult": {"count": "12", "idlist": ["12345678"]}},
            )
        assert request.url.path.endswith("/efetch.fcgi")
        assert request.url.params["id"] == "12345678"
        return httpx.Response(
            200,
            text=_PUBMED_FETCH_XML,
            headers={"Content-Type": "application/xml"},
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.search(
        BiomedicalSearchRequest(
            provider="pubmed",
            query="cancer biomarkers",
            count=1,
            page=2,
            publication_year=2024,
        )
    )
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.BIOMEDICAL_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.provider == "pubmed"
    assert result.total_results == 12
    assert result.results[0].paper_id == "12345678"
    assert result.results[0].pmcid == "PMC12345"
    assert result.results[0].authors == ["Ada Lovelace", "Research Team"]
    assert evidence[0].evidence_type == "pubmed_search_response"


def test_europe_pmc_search_returns_bounded_normalized_results(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/europepmc/webservices/rest/search")
        assert request.url.params["query"] == "gene therapy PUB_YEAR:2024"
        assert request.url.params["pageSize"] == "1"
        return httpx.Response(
            200,
            json={
                "hitCount": 5,
                "resultList": {
                    "result": [
                        {
                            "id": "9876543",
                            "pmid": "9876543",
                            "pmcid": "PMC98765",
                            "title": "Gene therapy under bounded controls",
                            "abstractText": "Abstract from Europe PMC",
                            "authorString": "Ada Lovelace; Grace Hopper",
                            "journalTitle": "Bio Journal",
                            "pubYear": "2024",
                            "firstPublicationDate": "2024-02-01",
                            "doi": "10.2000/example",
                            "citedByCount": 8,
                            "isOpenAccess": "Y",
                        }
                    ]
                },
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.search(
        BiomedicalSearchRequest(
            provider="europe_pmc",
            query="gene therapy",
            count=1,
            publication_year=2024,
        )
    )
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.BIOMEDICAL_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.provider == "europe_pmc"
    assert result.results[0].paper_id == "9876543"
    assert result.results[0].is_open_access is True
    assert str(result.results[0].source_url) == "https://europepmc.org/article/PMC/PMC98765"
    assert evidence[0].evidence_type == "europe_pmc_search_response"


def test_pubmed_get_paper_returns_normalized_metadata(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/efetch.fcgi")
        return httpx.Response(
            200,
            text=_PUBMED_FETCH_XML,
            headers={"Content-Type": "application/xml"},
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_paper(BiomedicalPaperRequest(provider="pubmed", paper_id="12345678"))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.BIOMEDICAL_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.paper.title == "Bounded biomedical agents"
    assert result.paper.doi == "10.1000/biomed"
    assert result.paper.abstract.startswith("Background:")
    assert evidence[0].evidence_type == "pubmed_paper_response"


def test_europe_pmc_get_paper_rejects_malformed_payloads(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hitCount": 1, "resultList": {"result": [{"id": "1"}]}})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="title"):
        plugin.get_paper(BiomedicalPaperRequest(provider="europe_pmc", paper_id="1"))


def test_search_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.search(BiomedicalSearchRequest(provider="pubmed", query="cancer biomarkers"))


def test_search_rejects_counts_above_max_results(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="configured maximum"):
        plugin.search(BiomedicalSearchRequest(provider="pubmed", query="x", count=6))


def test_get_paper_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.get_paper(BiomedicalPaperRequest(provider="pubmed", paper_id="123"))


def test_search_surfaces_transport_failures_as_plugin_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="unavailable"):
        plugin.search(BiomedicalSearchRequest(provider="pubmed", query="cancer biomarkers"))


@pytest.mark.parametrize(
    ("provider", "expected_event"),
    [
        ("pubmed", "pubmed_search_failed"),
        ("europe_pmc", "europe_pmc_search_failed"),
    ],
)
def test_search_records_provider_specific_failure_events(
    tmp_path: Path,
    provider: str,
    expected_event: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, ledger_service = make_plugin(
        tmp_path,
        handler=httpx.MockTransport(handler),
    )

    with pytest.raises(BiomedicalResearchPluginError, match="unavailable"):
        plugin.search(BiomedicalSearchRequest(provider=provider, query="cancer"))

    assert audit_event_payloads(ledger_service)[-1]["event_name"] == expected_event


@pytest.mark.parametrize(
    ("provider", "expected_event"),
    [
        ("pubmed", "pubmed_paper_lookup_failed"),
        ("europe_pmc", "europe_pmc_paper_lookup_failed"),
    ],
)
def test_get_paper_records_provider_specific_failure_events(
    tmp_path: Path,
    provider: str,
    expected_event: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, ledger_service = make_plugin(
        tmp_path,
        handler=httpx.MockTransport(handler),
    )

    with pytest.raises(BiomedicalResearchPluginError, match="unavailable"):
        plugin.get_paper(BiomedicalPaperRequest(provider=provider, paper_id="123"))

    assert audit_event_payloads(ledger_service)[-1]["event_name"] == expected_event


def test_provider_label_returns_stable_values(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin._provider_label("pubmed") == "PubMed"
    assert plugin._provider_label("europe_pmc") == "Europe PMC"


def test_search_pubmed_rejects_non_object_payload(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["bad"])

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="JSON object"):
        plugin._search_pubmed(BiomedicalSearchRequest(provider="pubmed", query="x"))


def test_search_pubmed_rejects_missing_esearchresult(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="esearchresult"):
        plugin._search_pubmed(BiomedicalSearchRequest(provider="pubmed", query="x"))


def test_search_pubmed_rejects_non_list_idlist(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"esearchresult": {"idlist": "123"}})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="idlist must be a list"):
        plugin._search_pubmed(BiomedicalSearchRequest(provider="pubmed", query="x"))


def test_search_pubmed_returns_empty_results_without_fetch(tmp_path: Path) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(
            200,
            json={"esearchresult": {"count": "0", "idlist": []}},
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    results, total, payload = plugin._search_pubmed(
        BiomedicalSearchRequest(provider="pubmed", query="x")
    )

    assert results == []
    assert total == 0
    assert requests == ["/entrez/eutils/esearch.fcgi"]
    assert "search" in payload


def test_get_pubmed_paper_raises_when_no_matching_paper_returned(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<PubmedArticleSet />")

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="no matching paper"):
        plugin._get_pubmed_paper("123")


def test_pubmed_term_includes_publication_year_filter(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin._pubmed_term("  gene   therapy ", 2024) == "gene therapy AND 2024[pdat]"


def test_search_europe_pmc_rejects_non_object_payload(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["bad"])

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="JSON object"):
        plugin._search_europe_pmc(
            BiomedicalSearchRequest(provider="europe_pmc", query="x")
        )


def test_get_europe_pmc_paper_rejects_non_object_payload(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["bad"])

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="JSON object"):
        plugin._get_europe_pmc_paper("123")


def test_get_europe_pmc_paper_raises_when_no_matching_result_returned(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"hitCount": 0, "resultList": {"result": []}},
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="no matching paper"):
        plugin._get_europe_pmc_paper("123")


def test_europe_pmc_query_includes_publication_year_filter(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin._europe_pmc_query("  gene   therapy ", 2024) == "gene therapy PUB_YEAR:2024"


def test_normalize_europe_pmc_results_tolerates_missing_hit_count_and_skips_bad_items(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    results, total = plugin._normalize_europe_pmc_results(
        {
            "hitCount": "unknown",
            "resultList": {
                "result": [
                    "bad",
                    {
                        "id": "123",
                        "title": " Example ",
                        "abstractText": "Body",
                        "authorString": "Ada Lovelace",
                    },
                ]
            },
        },
        limit=5,
    )

    assert total is None
    assert len(results) == 1
    assert results[0].paper_id == "123"


def test_parse_pubmed_articles_rejects_malformed_xml(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(BiomedicalResearchPluginError, match="valid XML"):
        plugin._parse_pubmed_articles("<PubmedArticleSet>", limit=1)


def test_parse_pubmed_article_keeps_abstract_sections_in_order(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    root = ET.fromstring(_PUBMED_FETCH_XML)
    article = root.find("./PubmedArticle")
    assert article is not None

    result = plugin._parse_pubmed_article(article)

    assert result.abstract.startswith("Background: Agents help with discovery.")
    assert "They stay bounded and auditable." in result.abstract


def test_europe_pmc_normalization_trims_blank_optional_strings_to_none(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    item = plugin._normalize_europe_pmc_item(
        {
            "id": "123",
            "title": " Example ",
            "abstractText": "Body",
            "journalTitle": "   ",
            "doi": "  ",
            "pmid": "  ",
            "pmcid": "  ",
        }
    )

    assert item.journal is None
    assert item.doi is None
    assert item.pmid is None
    assert item.pmcid is None
    assert item.source_url is None


def test_pubmed_identifier_helpers_skip_blank_and_missing_values(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    root = ET.fromstring(
        """
        <PubmedArticle>
          <PubmedData>
            <ArticleIdList>
              <ArticleId IdType="doi"> </ArticleId>
              <ArticleId IdType="pmc">PMC123</ArticleId>
            </ArticleIdList>
          </PubmedData>
        </PubmedArticle>
        """
    )

    doi, pmcid = plugin._pubmed_identifiers(root)

    assert doi is None
    assert pmcid == "PMC123"


def test_scalar_helpers_tolerate_malformed_values_safely(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin._to_int("abc") is None
    assert plugin._to_int(7) == 7
    assert plugin._string_or_none("  ") is None
    assert plugin._first_string(None, "  ", "value") == "value"
    assert plugin._bool_from_yn(" maybe ") is None


def test_publication_date_uses_medline_date_fallback(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    article = ET.fromstring(
        """
        <Article>
          <Journal>
            <JournalIssue>
              <PubDate>
                <MedlineDate>2024 Spring</MedlineDate>
              </PubDate>
            </JournalIssue>
          </Journal>
        </Article>
        """
    )

    assert plugin._pubmed_publication_date(article) == "2024 Spring"

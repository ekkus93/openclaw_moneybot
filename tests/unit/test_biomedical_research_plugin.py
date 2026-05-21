"""Unit tests for the biomedical research plugin."""

from __future__ import annotations

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


def test_search_surfaces_transport_failures_as_plugin_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BiomedicalResearchPluginError, match="unavailable"):
        plugin.search(BiomedicalSearchRequest(provider="pubmed", query="cancer biomarkers"))

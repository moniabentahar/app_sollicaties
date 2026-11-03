"""Tests for src.enrich — vacancy text fetching and summaries (network mocked)."""

from types import SimpleNamespace

import src.enrich as enrich
from src.filters import TIER_LOW, TIER_STRONG
from src.models import JobListing, ScoredListing

LI_URL = "https://be.linkedin.com/jobs/view/direction-marketing-at-x-4457793076"
LI_PAGE = '<div class="show-more-less-html__markup">Vous dirigez le <b>marketing</b>.<br>Français et anglais.</div>'


def _listing(url: str, site: str = "linkedin", desc: str = "") -> JobListing:
    return JobListing(title="Direction Marketing", company="X", location="Chimay, Belgium",
                      source_site=site, apply_url=url, description_summary=desc)


class TestFetchDescriptions:
    def test_linkedin_uses_guest_api_and_fills_text(self, monkeypatch):
        calls = []
        monkeypatch.setattr(enrich, "_get", lambda url, accept="text/html": calls.append(url) or LI_PAGE)
        out, texts = enrich.fetch_descriptions([_listing(LI_URL)])
        assert calls == ["https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4457793076"]
        assert "Français et anglais" in out[0].description_summary
        assert LI_URL in texts

    def test_existing_description_is_kept_and_not_fetched(self, monkeypatch):
        monkeypatch.setattr(enrich, "_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetched")))
        listing = _listing(LI_URL, desc="Al een samenvatting.")
        out, texts = enrich.fetch_descriptions([listing])
        assert out == [listing] and texts == {}

    def test_jsonld_jobposting_is_clean_text(self, monkeypatch):
        page = ('<script type="application/ld+json">{"@type":"JobPosting",'
                '"description":"&lt;p&gt;Brand manager role&lt;/p&gt;"}</script>')
        monkeypatch.setattr(enrich, "_get", lambda *a, **k: page)
        out, _ = enrich.fetch_descriptions([_listing("https://www.randstad.be/job/1/", "randstad")])
        assert out[0].description_summary == "Brand manager role"

    def test_page_without_jobposting_is_not_used_for_scoring(self, monkeypatch):
        page = "<html><body><nav>Menu marketing</nav><main>Communicatiespecialist gezocht</main></body></html>"
        monkeypatch.setattr(enrich, "_get", lambda *a, **k: page)
        url = "https://werkenvoor.be/nl/jobs/1"
        out, texts = enrich.fetch_descriptions([_listing(url, "werkenvoor")])
        assert out[0].description_summary == ""
        assert texts[url] == "Communicatiespecialist gezocht"

    def test_fetch_failure_leaves_listing_unchanged(self, monkeypatch):
        monkeypatch.setattr(enrich, "_get", lambda *a, **k: "")
        listing = _listing(LI_URL)
        out, texts = enrich.fetch_descriptions([listing])
        assert out == [listing] and texts == {}


class _FakeClient:
    def __init__(self, answer: str):
        self.calls = 0
        self.messages = SimpleNamespace(create=self._create)
        self._answer = answer

    def _create(self, **_):
        self.calls += 1
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._answer)])


class TestSummarizeListings:
    def test_relevant_listing_gets_llm_summary_low_gets_snippet(self):
        long_text = "Eerste zin over de job. " + "x " * 400
        strong = ScoredListing(_listing("u1", desc="tekst"), 8, [], TIER_STRONG)
        low = ScoredListing(_listing("u2", desc=long_text), 2, [], TIER_LOW)
        client = _FakeClient("Korte samenvatting.")
        out = enrich.summarize_listings([strong, low], {"u1": "tekst", "u2": long_text}, "key", lambda k: client)
        assert out[0].listing.description_summary == "Korte samenvatting."
        assert client.calls == 1
        assert out[1].listing.description_summary.startswith("Eerste zin over de job.")
        assert len(out[1].listing.description_summary) <= enrich._SNIPPET_CHARS + 1

    def test_geen_answer_means_no_summary(self):
        s = ScoredListing(_listing("u1"), 8, [], TIER_STRONG)
        out = enrich.summarize_listings([s], {"u1": "cookie banner"}, "key", lambda k: _FakeClient("GEEN"))
        assert out[0].listing.description_summary == ""

    def test_listings_without_fetched_text_are_untouched(self):
        s = ScoredListing(_listing("u1", desc="origineel"), 8, [], TIER_STRONG)
        assert enrich.summarize_listings([s], {}, "key") == [s]

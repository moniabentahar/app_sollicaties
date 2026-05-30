"""Tests for JobListing and ScoredListing dataclasses."""

from src.models import JobListing, ScoredListing


def _listing(**kwargs) -> JobListing:
    defaults = dict(title="Brand Manager", company="Acme NV", location="Brussels", source_site="vdab")
    return JobListing(**{**defaults, **kwargs})


def test_job_listing_defaults():
    job = _listing()
    assert job.remote == "unknown"
    assert job.languages == []
    assert job.skills == []
    assert job.experience_level == ""


def test_job_listing_as_dict_joins_lists():
    job = _listing(languages=["Dutch", "French"], skills=["brand management", "sponsorship"])
    d = job.as_dict()
    assert d["languages"] == "Dutch|French"
    assert d["skills"] == "brand management|sponsorship"


def test_job_listing_as_dict_keys():
    job = _listing()
    d = job.as_dict()
    expected_keys = {
        "title", "company", "location", "source_site",
        "remote", "experience_level", "languages", "skills",
        "posted_date", "apply_url", "description_summary",
    }
    assert expected_keys == set(d.keys())


def test_scored_listing_as_dict_includes_score_and_tier():
    job = _listing()
    scored = ScoredListing(listing=job, score=9, flags=["✓ title match", "✓ Belgium"], tier="strong")
    d = scored.as_dict()
    assert d["score"] == 9
    assert d["tier"] == "strong"
    assert "✓ title match" in d["flags"]
    assert "✓ Belgium" in d["flags"]


def test_scored_listing_empty_flags():
    job = _listing()
    scored = ScoredListing(listing=job, score=0, flags=[], tier="low")
    assert scored.as_dict()["flags"] == ""

"""Data models for job listings and scored results."""

from dataclasses import dataclass, field


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    source_site: str
    remote: str = "unknown"          # remote | hybrid | onsite | unknown
    experience_level: str = ""
    languages: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    posted_date: str = ""
    apply_url: str = ""
    description_summary: str = ""

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source_site": self.source_site,
            "remote": self.remote,
            "experience_level": self.experience_level,
            "languages": "|".join(self.languages),
            "skills": "|".join(self.skills),
            "posted_date": self.posted_date,
            "apply_url": self.apply_url,
            "description_summary": self.description_summary,
        }


@dataclass
class ScoredListing:
    listing: JobListing
    score: int
    flags: list[str] = field(default_factory=list)
    tier: str = ""    # strong | consider | low

    def as_dict(self) -> dict:
        d = self.listing.as_dict()
        d["score"] = self.score
        d["flags"] = "  ".join(self.flags)
        d["tier"] = self.tier
        return d

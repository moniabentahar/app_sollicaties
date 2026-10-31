"""Tests for the scoring and filtering engine."""

from src.models import JobListing
from src.profile import CORE_SKILLS
from src.filters import (
    filter_and_score,
    score_listing,
    TIER_STRONG,
    TIER_CONSIDER,
    TIER_LOW,
)


def _listing(**kwargs) -> JobListing:
    defaults = dict(
        title="Marketing Manager",
        company="Acme NV",
        location="Brussels, Belgium",
        source_site="indeed",
    )
    return JobListing(**{**defaults, **kwargs})


# --- Title scoring ---

class TestTitleScoring:
    def test_exact_title_adds_three(self):
        scored = score_listing(_listing(title="Marketing Manager"))
        assert "[+] title match" in scored.flags

    def test_cmo_title_matches(self):
        scored = score_listing(_listing(title="CMO"))
        assert "[+] title match" in scored.flags

    def test_head_of_marketing_matches(self):
        scored = score_listing(_listing(title="Head of Marketing"))
        assert "[+] title match" in scored.flags

    def test_sales_rep_no_title_bonus(self):
        scored = score_listing(_listing(title="Sales Representative"))
        assert "[+] title match" not in scored.flags


# --- Geography scoring ---

class TestGeographyScoring:
    def test_belgium_location_flagged(self):
        scored = score_listing(_listing(location="Ghent, Belgium"))
        assert "[+] Belgium" in scored.flags

    def test_brussels_flagged(self):
        scored = score_listing(_listing(location="Brussels"))
        assert "[+] Belgium" in scored.flags

    def test_remote_flagged(self):
        scored = score_listing(_listing(location="Anywhere", remote="remote"))
        assert "[+] remote/hybrid" in scored.flags

    def test_hybrid_flagged(self):
        scored = score_listing(_listing(remote="hybrid", location="London"))
        assert "[+] remote/hybrid" in scored.flags

    def test_onsite_amsterdam_penalised(self):
        scored = score_listing(_listing(location="Amsterdam, Netherlands", remote="onsite"))
        assert "[!] outside Belgium / not remote" in scored.flags

    def test_belgium_description_also_counts(self):
        scored = score_listing(_listing(
            location="Unspecified",
            description_summary="Based in Antwerp, Belgium.",
        ))
        assert "[+] Belgium" in scored.flags


# --- Language scoring ---

class TestLanguageScoring:
    def test_dutch_listed_adds_bonus(self):
        scored = score_listing(_listing(languages=["Dutch", "French"]))
        assert "[+] Dutch/French required" in scored.flags

    def test_nl_abbreviation_counted(self):
        scored = score_listing(_listing(languages=["NL", "EN"]))
        assert "[+] Dutch/French required" in scored.flags

    def test_english_only_no_lang_bonus(self):
        scored = score_listing(_listing(languages=["English"]))
        assert "[+] Dutch/French required" not in scored.flags

    def test_french_in_description_counted(self):
        scored = score_listing(_listing(description_summary="Candidate must speak French and Dutch."))
        assert "[+] Dutch/French required" in scored.flags


# --- Exclusion penalties ---

class TestExclusionPenalties:
    def test_junior_title_penalised(self):
        good = score_listing(_listing(title="Marketing Manager"))
        bad = score_listing(_listing(title="Junior Marketing Manager"))
        assert bad.score < good.score
        assert "[!] junior/entry-level" in bad.flags

    def test_internship_penalised(self):
        scored = score_listing(_listing(title="Marketing Internship"))
        assert "[!] junior/entry-level" in scored.flags

    def test_stagiaire_penalised(self):
        scored = score_listing(_listing(description_summary="Offre de stage pour stagiaire."))
        assert "[!] junior/entry-level" in scored.flags


# --- Skill scoring ---

class TestSkillScoring:
    def test_skills_in_listing_add_score(self):
        base = score_listing(_listing())
        with_skills = score_listing(_listing(skills=["brand management", "sponsorship", "event management"]))
        assert with_skills.score > base.score

    def test_skill_bonus_capped_at_four(self):
        # Seven skills straight from the active CV profile, so the test doesn't
        # break when a new CV changes the skill names.
        many_skills = score_listing(_listing(skills=sorted(CORE_SKILLS)[:7]))
        assert "[+] 4 skill(s) matched" in many_skills.flags


# --- Tier assignment ---

class TestTiers:
    def test_perfect_listing_is_strong(self):
        scored = score_listing(_listing(
            title="Marketing Manager",
            location="Brussels, Belgium",
            languages=["Dutch", "French"],
            skills=["brand management", "sponsorship", "event management"],
        ))
        assert scored.tier == TIER_STRONG

    def test_offsite_no_remote_is_low(self):
        scored = score_listing(_listing(
            title="Sales Clerk",
            location="Tokyo, Japan",
            remote="onsite",
        ))
        assert scored.tier == TIER_LOW

    def test_filter_and_score_sorted_descending(self):
        listings = [
            _listing(title="Sales Rep", location="London", remote="onsite"),
            _listing(title="Marketing Manager", location="Brussels, Belgium", languages=["Dutch"]),
        ]
        result = filter_and_score(listings)
        assert result[0].score >= result[1].score

    def test_filter_and_score_returns_all(self):
        listings = [_listing() for _ in range(5)]
        result = filter_and_score(listings)
        assert len(result) == 5


# --- Seniority / level ---

class TestSeniority:
    def test_senior_title_outranks_specialist(self):
        manager = score_listing(_listing(title="Marketing Manager"))
        specialist = score_listing(_listing(title="Marketing Specialist"))
        assert manager.score == specialist.score + 2
        assert "[+] senior level" in manager.flags

    def test_dutch_compound_manager_is_senior(self):
        scored = score_listing(_listing(title="Communicatiemanager"))
        assert "[+] senior level" in scored.flags
        assert scored.tier == TIER_STRONG

    def test_coordinator_is_below_level(self):
        scored = score_listing(_listing(title="Content Coordinator"))
        assert "[!] below level" in scored.flags
        assert scored.tier == TIER_LOW

    def test_specialist_in_belgium_is_consider(self):
        scored = score_listing(_listing(title="PR & Communications Specialist"))
        assert scored.tier == TIER_CONSIDER

    def test_assistant_title_capped_low(self):
        scored = score_listing(_listing(
            title="Vastgoed - Sales & Marketing assistant",
            remote="hybrid",
            languages=["Dutch", "French"],
        ))
        assert "[!] junior/entry-level" in scored.flags
        assert scored.score <= 3
        assert scored.tier == TIER_LOW

    def test_jr_title_capped_low(self):
        scored = score_listing(_listing(title="Jr Marketing & Communication Specialist"))
        assert scored.tier == TIER_LOW

    def test_assistant_in_description_not_penalised(self):
        scored = score_listing(_listing(description_summary="You manage an assistant."))
        assert "[!] junior/entry-level" not in scored.flags


# --- Non-marketing roles that mention marketing words ---

class TestDomainExclusions:
    def test_recruitment_consultant_not_a_match(self):
        scored = score_listing(_listing(title="Recruitment Consultant Sales & Marketing"))
        assert "[+] title match" not in scored.flags
        assert scored.tier == TIER_LOW

    def test_unified_communications_product_owner_not_a_match(self):
        scored = score_listing(_listing(title="Product Owner — Unified Communications UX"))
        assert scored.tier == TIER_LOW

    def test_consulting_partner_not_a_partnership_role(self):
        scored = score_listing(_listing(title="Partner, Safe and Sustainable Operations, Belgium"))
        assert scored.tier == TIER_LOW

    def test_partnership_manager_still_matches(self):
        scored = score_listing(_listing(title="Strategic Partnership Manager"))
        assert scored.tier == TIER_STRONG

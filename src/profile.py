"""the candidate's candidate profile — single source of truth for all scoring decisions."""

CANDIDATE_NAME = "the candidate"
CANDIDATE_LOCATION = "Belgium, Belgium (West Flanders)"

TARGET_TITLES: frozenset[str] = frozenset({
    "marketing manager",
    "brand manager",
    "sponsorship manager",
    "head of marketing",
    "cmo",
    "chief marketing officer",
    "marketing director",
    "brand director",
    "communications manager",
    "marketing communications manager",
    "director of marketing",
    "vp marketing",
    "vp of marketing",
})

CORE_SKILLS: frozenset[str] = frozenset({
    "brand management",
    "sponsorship",
    "marketing communication",
    "atl",
    "btl",
    "brand activation",
    "event management",
    "people management",
    "team management",
    "marketing strategy",
    "campaign management",
    "digital marketing",
    "media planning",
    "communications",
})

# Languages the candidate speaks — used to detect whether she qualifies
LANGUAGES: frozenset[str] = frozenset({
    "dutch", "nl", "nederlands",
    "french", "fr", "français", "francais",
    "english", "en", "anglais",
    "german", "de", "deutsch", "allemand",
})

# Dutch or French are native — flag roles that specifically need either
PREFERRED_LANGUAGES: frozenset[str] = frozenset({
    "dutch", "nl", "nederlands",
    "french", "fr", "français", "francais",
})

# Any listing containing these words gets a heavy penalty
EXCLUDE_KEYWORDS: frozenset[str] = frozenset({
    "junior",
    "entry level",
    "entry-level",
    "stage",
    "stagaire",
    "stagiaire",
    "internship",
    "intern",
    "trainee",
    "graduate",
    "starter",
    "0-2 years",
    "0-3 years",
    "1-2 years",
    "1-3 years",
    "student",
})

BELGIUM_INDICATORS: frozenset[str] = frozenset({
    "belgium", "belgique", "belgië", "belgie",
    "brussels", "bruxelles", "brussel",
    "antwerp", "anvers", "antwerpen",
    "ghent", "gent",
    "liège", "liege", "luik",
    "bruges", "brugge",
    "leuven", "louvain",
    "hasselt", "kortrijk", "mechelen",
    "namur", "namen",
    "west flanders", "west-vlaanderen",
    "east flanders", "oost-vlaanderen",
    "flemish", "vlaanderen",
    "wallonia", "wallonie",
    "charleroi", "mons", "bergen",
    "aalst", "sint-niklaas", "roeselare",
})

REMOTE_INDICATORS: frozenset[str] = frozenset({
    "remote", "télétravail", "teletravail",
    "thuiswerk", "hybrid", "hybride",
    "work from home", "wfh", "flexible",
})

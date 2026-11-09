"""Word lists used to read names in bylines, as data.

Input: nothing; this module only holds the lists.
Output: the sets `authors` looks words up in, all casefolded and without periods.

Lives here: which words are suffixes, titles, degrees, particles of a family name, marks of an
institution, and words worth a second look. Does not live here: how they are used (authors).
"""

SUFFIXES = {"jr": "Jr", "sr": "Sr", "ii": "II", "iii": "III", "iv": "IV"}
HONORIFICS = {"dr", "prof", "professor", "rev", "sen", "rep", "gov", "mr", "mrs", "ms", "sir"}
HONORIFICS |= {"rabbi", "msgr"}
DEGREES = {"md", "phd", "esq", "jd", "dds", "rn", "mba", "dvm", "mph"}

# Words that belong to the family name ('Jane van Doe').
PARTICLES = {"von", "van", "vanden", "de", "del", "della", "der", "den", "di", "da", "la", "le"}
PARTICLES |= {"du", "dos", "das", "ter", "ten", "bin", "ibn", "al", "el"}
# Of those, the ones that written with a capital are far more often a given name ('Al Doe').
GIVEN_WHEN_CAPITAL = {"al", "el", "da", "bin", "ibn", "ten"}
# Articles: alone, they are never a person's given name ('Le Monde').
ARTICLES = {"le", "la", "el", "il", "lo", "der", "die", "das", "les", "los", "las"}

# Words that mark an institution or a sentence, never part of a name written given-name first.
ORG_WORDS = {
    "anonymous", "board", "staff", "editor", "editors", "editorial", "editorials", "reader",
    "readers", "contributor", "contributors", "opinion", "opinions", "news", "press", "times",
    "post", "tribune", "globe", "journal", "service", "services", "show", "podcast", "writer",
    "writers", "bureau", "wire", "report", "reports", "team", "desk", "today", "newsday",
    "associated", "reuters", "bloomberg", "university", "institute", "center", "committee",
    "council", "association", "foundation", "network", "republic", "sentinel", "herald",
    "gazette", "syndicate", "special", "essay", "compiled", "columnist", "column", "star",
    "the", "of", "is", "from", "for", "with", "was", "are", "who", "his", "her", "its",
    "former", "director", "president", "chairman", "senator", "representative", "governor",
    "executive", "member", "author", "letters", "county", "department", "college", "coalition",
    "alliance", "society", "statesman", "dispatch", "courier", "chronicle", "register",
    "observer", "examiner", "inquirer", "weekly", "magazine", "ledger", "media", "inc", "llc",
    "company", "group", "excerpted", "illustration", "photo", "cartoon", "debate", "usa",
    "guest", "daily", "international", "national", "affairs", "studies", "advertiser",
}  # fmt: skip
# In 'Family, Given' form a one-word family name can be an ORG_WORD ('Press, Jane'), so only
# these words rule a part out when they stand alone before the comma.
ROLE_WORDS = {"staff", "board", "editors", "editorial", "readers", "anonymous", "opinion"}
ROLE_WORDS |= {"contributor", "contributors", "today", "democrat", "affairs", "studies"}
ROLE_WORDS |= {"advertiser"}

# Words of places and publications that are also family names ('Jane Washington'). A name
# holding one is read as a person, and listed for manual review (see `review_cases`).
WATCH_WORDS = {
    "sun", "bee", "courant", "dealer", "record", "union", "review", "mail", "telegraph",
    "guardian", "independent", "economist", "newsweek", "nation", "republican", "democrat",
    "advocate", "capital", "american", "city", "island", "beach", "park", "heights", "valley",
    "lake", "hills", "village", "station", "bay", "springs", "falls", "harbor", "square",
    "street", "avenue", "london", "paris", "tokyo", "jerusalem", "moscow", "washington",
    "boston", "chicago", "texas", "california", "florida", "york", "angeles", "jersey",
    "public", "life", "top", "council", "post", "press", "service", "senator",
}  # fmt: skip

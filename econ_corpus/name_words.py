"""Word lists used to read names in bylines, as data.

Input: nothing; this module only holds the lists.
Output: the sets `authors` looks words up in, all casefolded and without periods.

Lives here: which words are suffixes, titles, degrees, particles of a family name, marks of an
institution, and words worth a second look. Does not live here: how they are used (authors).
"""

SUFFIXES = {"jr": "Jr", "sr": "Sr", "ii": "II", "iii": "III", "iv": "IV"}
HONORIFICS = {"dr", "prof", "professor", "rev", "sen", "rep", "gov", "mr", "mrs", "ms", "sir"}
HONORIFICS |= {"rabbi", "msgr", "sister", "father", "pastor", "reverend", "doctor"}
# Offices and ranks written before a name ('State Rep Jane Doe', 'Vice President Jane Doe').
HONORIFICS |= {
    "state", "vice", "deputy", "former", "retired", "president", "senator", "representative",
    "governor", "mayor", "legis", "legislator", "assemb", "assemblyman", "assemblywoman", "ald",
    "alderman", "congressman", "congresswoman", "councilman", "councilwoman", "supervisor",
    "commissioner", "secretary", "ambassador", "general", "gen", "brigadier", "colonel", "col",
    "captain", "capt", "lieutenant", "lt", "sergeant", "sgt", "admiral",
}  # fmt: skip
DEGREES = {"md", "phd", "esq", "jd", "dds", "rn", "mba", "dvm", "mph"}

# Words that belong to the family name ('Jane van Doe').
PARTICLES = {"von", "van", "vanden", "de", "del", "della", "der", "den", "di", "da", "la", "le"}
PARTICLES |= {"du", "dos", "das", "ter", "ten", "bin", "ibn", "al", "el"}
# Of those, the ones that written with a capital are far more often a given name ('Al Doe').
GIVEN_WHEN_CAPITAL = {"al", "el", "da", "bin", "ibn", "ten"}
# Articles: alone, they are never a person's given name ('Le Monde').
ARTICLES = {"le", "la", "el", "der", "das", "los", "las"}  # not 'les', a given name

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
    # Towns that follow the name of a reader in letters to the editor.
    "manhattan", "brooklyn", "bronx", "queens", "mineola", "syosset", "huntington",
    "hempstead", "babylon", "massapequa", "smithtown", "islip", "bayside", "flushing",
    "freeport", "levittown", "hicksville", "merrick", "bellmore", "wantagh", "plainview",
    "commack", "patchogue", "riverhead", "oceanside", "jericho", "amityville", "copiague",
    "lindenhurst", "farmingdale", "bethpage", "woodmere", "northport", "setauket", "greenlawn",
    "whitestone", "sunnyside", "albany", "evanston", "naperville",
}  # fmt: skip

# Short forms of first names that are not simply their beginning ('Tim' for 'Timothy' needs
# no entry). Used only to list pairs of authors for review, never to merge them.
NICKNAMES = {
    "bill": {"william"}, "billy": {"william"}, "will": {"william"}, "bob": {"robert"},
    "bobby": {"robert"}, "rob": {"robert"}, "jim": {"james"}, "jimmy": {"james"},
    "joe": {"joseph"}, "joey": {"joseph"}, "jack": {"john"}, "johnny": {"john"},
    "dick": {"richard"}, "rick": {"richard"}, "rich": {"richard"}, "ted": {"edward", "theodore"},
    "ed": {"edward", "edwin", "edmund"}, "eddie": {"edward"}, "larry": {"lawrence", "laurence"},
    "chuck": {"charles"}, "charlie": {"charles"}, "steve": {"stephen", "steven"},
    "mike": {"michael"}, "tom": {"thomas"}, "tommy": {"thomas"}, "tony": {"anthony"},
    "dave": {"david"}, "andy": {"andrew"}, "drew": {"andrew"}, "al": {"albert", "alan", "alfred"},
    "hank": {"henry"}, "harry": {"harold", "henry"}, "jerry": {"gerald", "jerome"},
    "gene": {"eugene"}, "bernie": {"bernard"}, "danny": {"daniel"},
    "kate": {"katherine", "catherine"},
    "kathy": {"katherine", "kathleen"}, "cathy": {"catherine"}, "liz": {"elizabeth"},
    "beth": {"elizabeth"}, "betsy": {"elizabeth"}, "peggy": {"margaret"}, "meg": {"margaret"},
    "maggie": {"margaret"}, "sue": {"susan"}, "debbie": {"deborah"}, "jenny": {"jennifer"},
    "abe": {"abraham"}, "ben": {"benjamin"}, "fred": {"frederick", "alfred"}, "ron": {"ronald"},
    "ken": {"kenneth"}, "greg": {"gregory"}, "jeff": {"jeffrey", "geoffrey"},
    "pat": {"patrick", "patricia"},
}  # fmt: skip

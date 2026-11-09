"""Used by step 1 of the pipeline: the labels of a ProQuest export and how their values are read.

Input: the label of a field and its value, as exported.
Output: the column a label goes to, the compacted form used to compare categories, and the
parsed dates, years and ids with their status ('ok', 'missing', 'unparseable', ...).

Lives here: the label tables (Spanish label -> column), normalising metadata values and
parsing dates, years and ids. Does not live here: splitting a file into records (layout),
finding the fields of a record (fields) or building the table (parse).
"""

from datetime import date
import re

# English month prefixes, lower-cased: ProQuest writes dates like 'Nov 9, 2022' even though
# the labels are Spanish.
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

# Metadata labels we keep (Spanish label -> column).
KEPT_LABELS = {
    "Título": "title",
    "Autor": "author",
    "Título de publicación": "publication",
    "Año de publicación": "year_raw",
    "Fecha de publicación": "date_raw",
    "Sección": "section",
    "Idioma de la publicación": "language",
    "Tipo de fuente": "source_type",
    "Tipo de documento": "doc_type",
    "ID del documento de ProQuest": "id_raw",
}
# The other metadata labels (Spanish label -> column). They are kept as exported, unparsed.
# They must be recognised, otherwise the metadata walk (see `fields.read_metadata`) stops at
# them and the fields above them are lost into the body. The list was built from the data:
# the first full run showed which labels were missing.
EXTRA_LABELS = {
    "Materia": "subject",
    "Lugar": "location",
    "Personas": "people",
    "Empresa/organización": "organization",
    "Término de indexación de negocios": "business_index_term",
    "Identificador / palabra clave": "keyword",
    "Clasificación": "classification",
    "Lugar y fecha de origen": "origin_place_date",
    "Páginas": "pages",
    "Número de páginas": "page_count",
    "Primera página": "first_page",
    "ISSN": "issn",
    "CODEN": "coden",
    "Editorial": "publisher",
    "Lugar de publicación": "publication_place",
    "País de publicación": "publication_country",
    "Materia de publicación": "publication_subject",
    "URL del documento": "document_url",
    "Copyright": "copyright",
    "Última actualización": "last_updated",
    "Base de datos": "database",
    "Disponibilidad de texto completo": "fulltext_availability",
    "e-ISSN": "eissn",
    "columna": "column_name",
    "Número de acceso": "accession_number",
    "Fecha del hito": "milestone_date",
    "Características del documento": "document_features",
    "Detalles de fuente": "source_details",
    "Número": "issue",
    "Autor corporativo/institucional": "corporate_author",
    "Empresa": "company",
    "URL": "url",
    "Historial de publicaciones": "publication_history",
    "Nombre del producto": "product_name",
    "Tomo": "volume",
    "Año": "issue_year",
    "Etnicidad": "ethnicity",
    "Duración del clip": "clip_duration",
}
# Fields of the header, before 'Texto completo:': the document link is the first line that
# starts with http; the others are labelled.
HEADER_LABELS = {"Resumen": "abstract", "Enlaces": "links"}
HEADER_URL = "header_url"
# Columns that also get a `<column>_key` copy used to compare categories.
KEY_COLUMNS = ["language", "source_type", "doc_type", "publication"]


def compact(value: str) -> str:
    """Remove every whitespace character and casefold.

    ProQuest inserts stray spaces inside metadata values ('En glish'), so the compacted
    form is the safe key for comparing categories.
    """
    return re.sub(r"\s+", "", value).casefold()


# Labels are matched through `compact` too, so a stray space in a label does not break it.
LABEL_KEYS = {compact(k): v for k, v in (KEPT_LABELS | EXTRA_LABELS).items()}
HEADER_KEYS = {compact(k): v for k, v in HEADER_LABELS.items()}
METADATA_COLS = [*KEPT_LABELS.values(), *EXTRA_LABELS.values()]


def parse_int(raw: str | None, lo: int = 0, hi: int = 10**15) -> tuple[int | None, str]:
    """Parse a digits-only integer after removing stray spaces.

    Returns (value, status) where status is 'ok', 'missing' or 'unparseable'.
    """
    if raw is None:
        return None, "missing"
    digits = compact(raw)
    if digits.isascii() and digits.isdigit() and lo <= int(digits) <= hi:
        return int(digits), "ok"
    return None, "unparseable"


def parse_date(raw: str | None) -> tuple[date | None, int | None, str]:
    """Parse a publication date such as 'Nov 9, 2022', or a bare year.

    Returns (date, year, status) where status is 'ok', 'year_only', 'missing' or
    'unparseable'. A year-only value gives no date but keeps the year.
    """
    if raw is None:
        return None, None, "missing"
    text = compact(raw)
    if re.fullmatch(r"\d{4}", text):
        return None, int(text), "year_only"
    # After `compact` the date has no spaces: 'Nov 9, 2022' -> 'nov9,2022'.
    m = re.fullmatch(r"([a-z]{3,9})(\d{1,2}),(\d{4})", text)
    if m and m[1][:3] in MONTHS:
        try:
            parsed = date(int(m[3]), MONTHS.index(m[1][:3]) + 1, int(m[2]))
        except ValueError:  # impossible day, such as Feb 30
            return None, None, "unparseable"
        return parsed, parsed.year, "ok"
    return None, None, "unparseable"

# Shared by the datasheets

| File | What it does |
|---|---|
| `summaries.py` | Small facts about a record: the newspaper and the edition of a publication, whether a label, a section or a title marks opinion, the order of the export files; and how numbers are written |
| `tables.py` | The tables of the datasheets (counts by newspaper, year, document type, section, missing values) and writing a table as CSV or Markdown |
| `source_tables.py` | The tables of where the records come from: publications outside the queried newspapers, the online editions and their blog label, and the download dates |
| `figures.py` | The figures of the datasheets, drawn as SVG: bars per year, horizontal bars, the flow of the exclusions |
| `pipeline_figure.py` | The map of the pipelines for the overview datasheet, drawn as SVG |
| `pdf.py` | Renders a datasheet as PDF (`make pdf`, needs Google Chrome) |

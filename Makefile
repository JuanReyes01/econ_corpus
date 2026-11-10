#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = econ_corpus
PYTHON_VERSION = 3.12
PYTHON_INTERPRETER = uv run python

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	uv sync
	



## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


## Lint using ruff (use `make format` to do formatting)
.PHONY: lint
lint:
	uv run ruff format --check
	uv run ruff check

## Format source code with ruff
.PHONY: format
format:
	uv run ruff check --fix
	uv run ruff format



#################################################################################
# PIPELINE (run in this order; README.md explains each step)                    #
#################################################################################

RAW_DIR ?= /home/juanc/data/econ_corpus/raw/ProQuestDownloads
DELIVERY ?= /home/juanc/data/econ_corpus/delivery

# Each step reads what the one before wrote, so they never run side by side, even with -j.
.NOTPARALLEL:

## 1. Parse the ProQuest exports in RAW_DIR into data/interim/records.parquet (about 5 minutes)
.PHONY: parse
parse:
	uv run python -m econ_corpus.raw.parse $(RAW_DIR)


## 2. Give every parsed row one reason (needs step 1; applies data/review)
.PHONY: exclusions
exclusions:
	uv run python -m econ_corpus.raw.exclusions


## 3a. Write the raw table as a shareable CSV (needs step 2)
.PHONY: export
export:
	uv run python -m econ_corpus.raw.export


## 3b. Build the datasheet of the raw table (needs step 2)
.PHONY: datasheet
datasheet:
	uv run python -m econ_corpus.raw.datasheet


## 4. Write the cleaned tables: articles, authors and their links (needs step 2)
.PHONY: processed
processed:
	uv run python -m econ_corpus.clean.processed


## 5. List the author cases that need a manual review (needs step 4)
.PHONY: review-cases
review-cases:
	uv run python -m econ_corpus.clean.review_cases


## 6. Build the datasheet of the cleaned dataset (needs step 4)
.PHONY: datasheet-clean
datasheet-clean:
	uv run python -m econ_corpus.clean.datasheet_clean


## 6b. Build the overview datasheet of both pipelines, figures first (needs steps 2 and 4)
.PHONY: overview
overview:
	uv run python -m econ_corpus.overview


## Pipeline 1 from the records already parsed: steps 2 to 3b (same as `python -m econ_corpus.raw`)
.PHONY: raw
raw: exclusions export datasheet


## Step 2 and then pipeline 2: steps 4 to 6b (same as `python -m econ_corpus.clean` after step 2)
.PHONY: cleaned
cleaned: exclusions processed review-cases datasheet-clean overview


## Render the three datasheets as PDF (needs google-chrome)
.PHONY: pdf
pdf:
	uv run python -m econ_corpus.shared.pdf docs/datasheet.md docs/datasheet_raw.md docs/datasheet_clean.md


## 7. Check that every output on disk belongs to the current records, reasons and review
.PHONY: check
check:
	uv run python -m econ_corpus.check


## Copy the current outputs into the delivery folder DELIVERY (checks them and renders the PDFs)
# Everything is a copy, never a link: a later run of the pipeline must not change what was
# delivered. The three folders are written anew each time, so nothing old stays in them. `check` stops the delivery when an output is stale, so the files of one delivery
# belong to one state of the pipeline.
.PHONY: delivery
delivery: check pdf
	rm -rf $(DELIVERY)/1_raw_txt $(DELIVERY)/2_raw_csv $(DELIVERY)/3_clean
	mkdir -p $(DELIVERY)/2_raw_csv $(DELIVERY)/3_clean
	cp -r --reflink=auto $(RAW_DIR) $(DELIVERY)/1_raw_txt
	cp --reflink=auto data/processed/econ_corpus_raw.csv data/processed/econ_corpus_raw_reasons.csv $(DELIVERY)/2_raw_csv/
	cp docs/datasheet_raw.pdf reports/tables/exclusion_counts.csv $(DELIVERY)/2_raw_csv/
	cp --reflink=auto data/processed/clean/*.csv $(DELIVERY)/3_clean/
	cp data/processed/clean/manifest.json docs/datasheet_clean.pdf $(DELIVERY)/3_clean/
	mkdir -p $(DELIVERY)/3_clean/review
	cp data/review/byline_parts.csv data/review/author_pairs.csv $(DELIVERY)/3_clean/review/
	cp docs/review_readme.md $(DELIVERY)/3_clean/review/README.md
	cp docs/delivery_readme.md $(DELIVERY)/README.md
	cp docs/datasheet.pdf $(DELIVERY)/datasheet.pdf


## Run tests
.PHONY: test
test:
	uv run pytest tests


## Set up Python interpreter environment
.PHONY: create_environment
create_environment:
	uv venv --python $(PYTHON_VERSION)
	@echo ">>> New uv virtual environment created. Activate with:"
	@echo ">>> Windows: .\\\\.venv\\\\Scripts\\\\activate"
	@echo ">>> Unix/macOS: source ./.venv/bin/activate"
	



#################################################################################
# PROJECT RULES                                                                 #
#################################################################################



#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)

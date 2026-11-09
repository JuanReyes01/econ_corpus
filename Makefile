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
	uv run python -m econ_corpus.parse $(RAW_DIR)


## 2. Give every parsed row one reason (needs step 1; applies data/review)
.PHONY: exclusions
exclusions:
	uv run python -m econ_corpus.exclusions


## 3a. Write the raw table as a shareable CSV (needs step 2)
.PHONY: export
export:
	uv run python -m econ_corpus.export


## 3b. Build the datasheet of the raw table (needs step 2)
.PHONY: datasheet
datasheet:
	uv run python -m econ_corpus.datasheet


## 4. Write the cleaned tables: articles, authors and their links (needs step 2)
.PHONY: processed
processed:
	uv run python -m econ_corpus.processed


## 5. List the author cases that need a manual review (needs step 4)
.PHONY: review-cases
review-cases:
	uv run python -m econ_corpus.review_cases


## 6. Build the datasheet of the cleaned dataset (needs step 4)
.PHONY: datasheet-clean
datasheet-clean:
	uv run python -m econ_corpus.datasheet_clean


## Steps 2 to 3b in order: everything of the raw table
.PHONY: raw
raw: exclusions export datasheet


## Steps 2 and 4 to 6 in order: everything of the cleaned dataset
.PHONY: cleaned
cleaned: exclusions processed review-cases datasheet-clean


## Render the two datasheets as PDF (needs google-chrome)
.PHONY: pdf
pdf:
	uv run python -m econ_corpus.pdf docs/datasheet_raw.md docs/datasheet_clean.md


## Copy the current outputs into the delivery folder DELIVERY (renders the PDFs first)
# Everything is a copy, never a link: a later run of the pipeline must not change what was
# delivered, and the files of one delivery belong to one state of the pipeline.
.PHONY: delivery
delivery: pdf
	mkdir -p $(DELIVERY)/2_raw_csv $(DELIVERY)/3_clean
	test -e $(DELIVERY)/1_raw_txt || cp -r --reflink=auto $(RAW_DIR) $(DELIVERY)/1_raw_txt
	cp --reflink=auto --remove-destination data/processed/econ_corpus_raw.csv docs/datasheet_raw.pdf $(DELIVERY)/2_raw_csv/
	cp --reflink=auto --remove-destination data/processed/clean/*.csv docs/datasheet_clean.pdf $(DELIVERY)/3_clean/
	rm -rf $(DELIVERY)/3_clean/review
	cp -r data/review $(DELIVERY)/3_clean/review
	cp docs/delivery_readme.md $(DELIVERY)/README.md


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

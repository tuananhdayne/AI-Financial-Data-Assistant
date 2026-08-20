---
pretty_name: ViFinQA
language:
- vi
task_categories:
- question-answering
- table-question-answering
size_categories:
- 1K<n<10K
tags:
- finance
- financial-reasoning
- numerical-reasoning
- vietnamese
configs:
- config_name: default
  data_files:
  - split: train
    path: questions/questions.jsonl
---

# ViFinQA Dataset

## Dataset Description

ViFinQA is a corpus-level dataset for Vietnamese financial question answering and numerical reasoning over annual financial statements. This public release contains 1,012 Vietnamese questions and 1,973 OCR-extracted reports from 100 Vietnamese listed companies, covering 2015–2025.

The dataset can support document retrieval, retrieval-augmented generation (RAG), financial information extraction, table understanding, and corpus-level question answering. The companion [ViFinQA repository](https://github.com/DSKT-NOWJ/ViFinQA) provides generation, retrieval, reranking, answering, and evaluation code.

**Paper:** *ViFinQA: A Comprehensive and Challenging Benchmark for End-to-End Vietnamese Financial Reasoning*

### Dataset Summary

| Property | Value |
| --- | ---: |
| Questions | 1,012 |
| Financial reports | 1,973 |
| Companies / stock tickers | 100 |
| Time range | 2015–2025 |
| Language | Vietnamese |
| Question format | JSON Lines (`.jsonl`) |
| Report format | UTF-8 plain text with OCR and inline table markup |
| Report text size | approximately 363 MiB |

### Master 3-Station Pipeline Architecture & Official Benchmark Scores

The ViFinQA solution codebase is organized into **3 Modular Stations**:
1. **Trạm 1 (Document Level):** Filters 146,000 tables down to target report files (**`DOCS_F2MACRO = 0.9615 (96.15%)`** verified on official leaderboard).
2. **Trạm 2 (Table Level & Startline):** Pre-filters Top 25 tables via In-RAM BM25 + BGE-M3 Dense Vector Cosine Search and maps start lines `<report_id>|<start_line>` (`TABLES_F2MACRO`).
3. **Trạm 3 (Execution Level):** Safe Pandas code execution, `get_val` engine, unit scaling, and answer calculation (`EXECUTION_ACCURACY` & `ANSWER_ACCURACY`).

#### Official Leaderboard Verification (Stage 1)
- **`DOCS_F2MACRO`**: **`0.9615` (`96.15%`)**
- **`DOCS_PRECISION`**: **`0.9655` (`96.55%`)**
- **`DOCS_RECALL`**: **`0.9642` (`96.42%`)**
- **`DOCS_MRR5`**: **`0.9740` (`97.40%`)**

#### Command Line Interface (CLI)
```bash
# Run Table Retrieval F2 Macro (Trạm 2) -> generates submission_table_f2.zip / submission_table_f2_bge.zip
python main.py --mode station2

# Run Full Master Pipeline (Trạm 1 -> 2 -> 3) -> generates submission_final.zip
python main.py --mode full
```

### Usage

The dataset has no required Python dependency. Questions can be loaded with the standard library:

```python
import json
from pathlib import Path

data_root = Path("/path/to/this/dataset")

with (data_root / "questions" / "questions.jsonl").open(
    encoding="utf-8"
) as file:
    questions = [json.loads(line) for line in file if line.strip()]

statement_paths = sorted(
    (data_root / "financial_statements").glob("*/*/*/*.txt")
)

first_question = questions[0]
first_statement = statement_paths[0].read_text(
    encoding="utf-8", errors="replace"
)

print(first_question)
print(statement_paths[0])
print(first_statement[:500])
```

The question file can also be loaded with [Hugging Face Datasets](https://huggingface.co/docs/datasets/):

```python
from datasets import load_dataset

questions = load_dataset(
    "json",
    data_files="questions/questions.jsonl",
    split="train",
)
```

## Dataset Structure

```text
.
├── code_stock.csv
├── financial_statements/
│   └── TICKER/
│       └── YEAR/
│           └── DOCUMENT/
│               └── DOCUMENT_extracted.txt
└── questions/
    └── questions.jsonl
```

For example:

```text
financial_statements/
└── AAA/
    └── 2015/
        └── AAA_financial_statements_2015_consolidated/
            └── AAA_financial_statements_2015_consolidated_extracted.txt
```

Report names usually identify consolidated (`consolidated`) or separate/company-level (`separate`) statements. A small number of files use `aggregated`, a generic financial-statement name, or an explanatory-document name. Based on the file names, the release contains 957 consolidated, 954 separate, 7 aggregated, and 55 other or unlabeled reports.

### Data Instances

A row in `questions/questions.jsonl` has the following form:

```json
{
  "id": 1,
  "question": "Lãi tiền gửi năm 2018 của công ty mẹ CTCP Hàng không Vietjet (VJC) là bao nhiêu triệu đồng?"
}
```

Each report is stored as one text file. OCR output retains page boundaries and may encode detected tables as inline HTML:

```text
===== PAGE 1 =====
...
<table><tr><td>...</td></tr></table>
```

`code_stock.csv` maps stock tickers to company names:

```csv
Mã CK,Tên công ty
HPG,CTCP Tập đoàn Hòa Phát
VCB,Ngân hàng TMCP Ngoại thương Việt Nam
```

### Data Fields

#### `questions/questions.jsonl`

- `id`: integer identifier. IDs are unique and sequential from 1 to 1,012.
- `question`: Vietnamese financial question as a string.

#### `code_stock.csv`

- `Mã CK`: Vietnamese stock ticker.
- `Tên công ty`: company name.

#### `financial_statements/**/*.txt`

- Full OCR-extracted report text in UTF-8.
- The path provides the stock ticker, reporting year, document name, and usually the statement type.
- Monetary units and reporting conventions remain those of the source document.

### Data Splits and Labels

For Hugging Face loading and preview purposes, this package exposes all 1,012 questions as a single `train` split. This name is a packaging convention, not an official model-training split; the release does not prescribe a train, validation, and test partition. It also does not include answers, executable programs, gold evidence, normalized table CSVs, or difficulty labels. Researchers should define and publish their own splits when using this package for model development.

The companion ViFinQA codebase supports the four difficulty tiers `easy`, `medium`, `intermediate`, and `hard`, but those tier labels are not included in this release.

## Relationship to the ViFinQA Codebase

The [companion repository](https://github.com/DSKT-NOWJ/ViFinQA) describes ViFinQA v1 as 1,012 questions grounded in 1,973 reports and 143,815 normalized tables. The first two counts correspond to this release. The 143,815 normalized tables and the richer annotations expected by the evaluation pipeline are not included here.

Consequently, this directory cannot be passed directly to the companion CLI's paper-reproduction configurations. Those configurations expect an `ocr_filter/` corpus with per-report `table_N.csv` files, a `file_filter.csv`, and four annotated question JSONL files. Use this release directly for text-corpus experiments, or preprocess it into the layout documented by the companion repository before running its retrieval and evaluation commands.

## Dataset Creation

The financial reports are a selected subset of the [TiniX Vietnam OCR Annual Financial Statements](https://huggingface.co/datasets/tinixai/ocr_annual_financials) corpus. The source corpus contains Vietnamese annual financial-statement PDFs and their OCR text for listed companies from 2015–2025. Its dataset card reports 18,231 reports, 1,491 stock tickers, and approximately 194 GB of data.

For this release, the relevant OCR documents were selected for 100 companies and organized by stock ticker, reporting year, and document name. The question collection targets facts and numerical reasoning across these reports. See the companion ViFinQA repository for the question-generation and benchmark pipeline.

## Considerations for Using the Data

### Known Limitations

- OCR errors may affect Vietnamese diacritics, numbers, table structure, and reading order.
- Coverage is uneven across companies, years, and report types; the presence of a company in `code_stock.csv` does not imply that every report type exists for every year.
- Some company-year pairs have multiple reports or explanatory documents.
- Questions may require information from one or more reports and may involve arithmetic, unit conversion, or aggregation.
- The question-only release does not support supervised answer evaluation without separately obtained labels.
- The data covers reports through 2025 and should not be treated as current market information or financial advice.

### Responsible Use

The reports concern real companies and may contain names or signatures of company officers and auditors. Users should preserve source attribution, respect applicable data-protection and intellectual-property requirements, and manually verify OCR-derived values before using them in high-stakes settings.

## Additional Information

### Licensing Information

The underlying TiniX OCR corpus is released under the [Creative Commons Attribution-NonCommercial 4.0 International license](https://creativecommons.org/licenses/by-nc/4.0/) (CC BY-NC 4.0). Users must comply with its attribution and non-commercial-use conditions when using the financial-statement content.

No separate license file for the ViFinQA question annotations is included in this directory. Do not assume that the question annotations carry permissions broader than those explicitly granted by the dataset maintainers.

### Citation Information

Please cite both ViFinQA and the source OCR corpus. The public ViFinQA repository does not currently provide a complete paper BibTeX entry; the following repository citation can be used until the official paper citation is published:

```bibtex
@misc{vifinqa,
  title        = {ViFinQA: A Comprehensive and Challenging Benchmark for
                  End-to-End Vietnamese Financial Reasoning},
  author       = {{DSKT-NOWJ}},
  howpublished = {GitHub repository},
  url          = {https://github.com/DSKT-NOWJ/ViFinQA}
}
```

```bibtex
@dataset{tinix_ocr_annual_financials,
  author    = {{TiniX AI}},
  title     = {TiniX Vietnam OCR Annual Financial Statements (2015--2025)},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/tinixai/ocr_annual_financials}
}
```

## Acknowledgments

We thank TiniX AI for releasing the source Vietnamese OCR financial-statement corpus and the contributors to the ViFinQA benchmark and companion codebase.

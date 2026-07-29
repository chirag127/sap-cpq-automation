# SAP CPQ Automation

[![GitHub stars](https://img.shields.io/github/stars/chirag127/sap-cpq-automation?style=flat-square)](https://github.com/chirag127/sap-cpq-automation)
[![License](https://img.shields.io/github/license/chirag127/sap-cpq-automation?style=flat-square)](LICENSE)
[![GH Pages](https://img.shields.io/badge/site-live-brightgreen?style=flat-square)](https://sap-cpq-automation.oriz.in)

Python automation scripts for SAP CPQ (Configure, Price, Quote) — bulk category creation, product import, and data conversion utilities.

**Live:** https://sap-cpq-automation.oriz.in

## Scripts

| Script | Description |
|--------|-------------|
| `src/convert_json_to_excel.py` | Convert scraped product JSON to CPQ-importable Excel format |
| `src/cpq_category_uploader.py` | Bulk upload categories and products to SAP CPQ via REST API |
| `src/cpq_link_categories.py` | Two-pass category linking (fetch all IDs, then update parent refs) |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your CPQ credentials in .env
```

## Configuration

All credentials are loaded from environment variables. Copy `.env.example` to `.env` and fill in your SAP CPQ tenant URL, username, password, and domain.

**Never commit `.env` to git.** The `.gitignore` already excludes it.

## Data

- `data/agco_complete_data.json` — Sample product data (AGCO/Massey Ferguson catalog)
- `data/CPQ_Import_Final.xlsx` — Generated Excel import file

## Archive

`archive/` contains earlier versions and experimental scripts.

## License

MIT

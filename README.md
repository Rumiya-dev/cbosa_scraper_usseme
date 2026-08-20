# CBOSA Resilient Scraper

Python-based data collection pipeline for downloading and processing
administrative court decisions from the Polish CBOSA database.

## Project status

Prototype / proof of concept.

The system was designed for a very large dataset of approximately
2.4–2.5 million court decisions.

## Features

- CBOSA search pagination
- document ID collection
- HTML parsing with BeautifulSoup
- SQLite checkpointing
- duplicate protection
- retry and exponential backoff
- automatic HTTP session recovery
- resumable processing
- pending / done / failed document states
- parsing of Sentencja and Uzasadnienie while preserving HTML
- testing of alternative archival sources (Hugging Face, Common Crawl, Wayback Machine)

## Reliability test

A continuous test batch of 100 documents completed with:

- 100 successfully processed
- 0 failed

## Tech stack

- Python
- Requests
- BeautifulSoup
- lxml
- SQLite
- DuckDB
- Common Crawl / Wayback research

## Important

This repository contains a prototype and testing tools.
It does not contain the full CBOSA dataset.
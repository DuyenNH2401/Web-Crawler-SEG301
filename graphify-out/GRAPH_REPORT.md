# Graph Report - Web-Crawler-SEG301  (2026-09-22)

## Corpus Check
- Corpus is ~6,371 words - fits in a single context window. You may not need a graph.

## Summary
- 202 nodes · 359 edges · 10 communities
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Crawler Engine and Frontier
- Shared and General Adapters
- BBC and Regression Tests
- Database and Data Models
- Project Architecture
- BBC Parsing Pipeline
- CLI and Digest Workflow
- Guardian Adapter
- Global Times Adapter
- Generic HTML Parser

## God Nodes (most connected - your core abstractions)
1. `SourceAdapter` - 22 edges
2. `CrawlerEngine` - 13 edges
3. `URLFrontier` - 11 edges
4. `BBCSource` - 10 edges
5. `Multi-source Focused Web Crawler` - 10 edges
6. `get_connection()` - 8 edges
7. `Article` - 8 edges
8. `Digest` - 8 edges
9. `CNNSource` - 8 edges
10. `GuardianSource` - 7 edges

## Surprising Connections (you probably didn't know these)
- `Requests` --semantically_similar_to--> `requests >= 2.31.0`  [INFERRED] [semantically similar]
  README.md → requirements.txt
- `BeautifulSoup` --semantically_similar_to--> `beautifulsoup4 >= 4.12.0`  [INFERRED] [semantically similar]
  README.md → requirements.txt
- `requirements.txt` --semantically_similar_to--> `Python Dependency Manifest`  [INFERRED] [semantically similar]
  README.md → requirements.txt
- `CrawlerEngine` --uses--> `SourceAdapter`  [INFERRED]
  crawler.py → sources/base.py
- `CrawlerLimitTests` --uses--> `CrawlerEngine`  [INFERRED]
  tests/test_crawler.py → crawler.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crawl Storage Model** — readme_pages_table, readme_links_table, readme_digests_table [EXTRACTED 1.00]

## Communities (10 total, 0 thin omitted)

### Community 0 - "Crawler Engine and Frontier"
Cohesion: 0.08
Nodes (21): collections, CrawlerEngine, Shared BFS crawler engine for all configured news-source adapters., Cache robots.txt decisions per host, matching the original crawler., Run the same crawl loop against any source adapter., RobotsManager, Article, requests (+13 more)

### Community 1 - "Shared and General Adapters"
Cohesion: 0.10
Nodes (10): re, Small adapter contract used by the shared crawler engine., SourceAdapter, CNNSource, is_cnn_health_article(), CNN adapter preserving the original CNN Health URL rule., remove_excluded_elements(), Source-specific adapters for the shared crawler. (+2 more)

### Community 2 - "BBC and Regression Tests"
Cohesion: 0.10
Nodes (8): BBCSource, BBCConfigurationTests, CrawlerLimitTests, _Response, _Session, _Source, unittest, unittest_mock

### Community 3 - "Database and Data Models"
Cohesion: 0.13
Nodes (20): Connection, get_connection(), get_summary_stats(), init_db(), insert_digest(), insert_links(), insert_page(), Any (+12 more)

### Community 4 - "Project Architecture"
Cohesion: 0.10
Nodes (22): Common Article Format, Articles per Source Limit, BeautifulSoup, Breadth-First Search Crawling Policy, collections.deque, digest.py, digests Table, links Table (+14 more)

### Community 5 - "BBC Parsing Pipeline"
Cohesion: 0.25
Nodes (17): BeautifulSoup, _canonicalize_link(), _clean_text(), extract_and_filter_links(), _extract_article_content(), _extract_title(), _extract_topic_content(), add_card() (+9 more)

### Community 6 - "CLI and Digest Workflow"
Cohesion: 0.19
Nodes (10): argparse, Configuration settings for the Focused Web Crawler. Topic: News & Information…, digest, build_digest(), main(), Run all five source crawlers and write one combined digest., os, sqlite3 (+2 more)

### Community 7 - "Guardian Adapter"
Cohesion: 0.23
Nodes (9): extract_links(), extract_page_data(), GuardianSource, is_allowed_domain(), is_blocked_subdomain(), is_crawlable(), make_soup(), normalize_url() (+1 more)

### Community 8 - "Global Times Adapter"
Cohesion: 0.26
Nodes (9): datetime, extract_links(), extract_page_info(), GlobalTimesSource, is_allowed_domain(), is_valid_url(), normalize_domain(), normalize_url() (+1 more)

### Community 9 - "Generic HTML Parser"
Cohesion: 0.20
Nodes (11): bs4, extract_and_filter_links(), is_article_url(), is_domain_allowed(), parse_page_data(), Any, HTML parsing and link extraction/filtering module using BeautifulSoup. Tasks 4…, Extract hyperlinks from HTML and apply filtering rules (Task 5): 1. Resolve… (+3 more)

## Knowledge Gaps
- **8 isolated node(s):** `News & Information`, `Common Article Format`, `collections.deque`, `Source-specific URL Filtering Rules`, `RobotFileParser` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 79 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SourceAdapter` connect `Shared and General Adapters` to `Crawler Engine and Frontier`, `BBC and Regression Tests`, `BBC Parsing Pipeline`, `Guardian Adapter`, `Global Times Adapter`?**
  _High betweenness centrality (0.217) - this node is a cross-community bridge._
- **Why does `Multi-source Focused Web Crawler` connect `Project Architecture` to `CLI and Digest Workflow`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `CrawlerEngine` (e.g. with `Article` and `SourceAdapter`) actually correct?**
  _`CrawlerEngine` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `News & Information`, `Common Article Format`, `collections.deque` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Crawler Engine and Frontier` be split into smaller, more focused modules?**
  _Cohesion score 0.08021390374331551 - nodes in this community are weakly interconnected._
- **Should `Shared and General Adapters` be split into smaller, more focused modules?**
  _Cohesion score 0.09788359788359788 - nodes in this community are weakly interconnected._
- **Should `BBC and Regression Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
# BBC Crawl Rule System

This crawler starts at `https://www.bbc.co.uk/business` and stores editorial
text from BBC articles and topic/index pages. It does not store images,
video/audio, captions, advertisements, bylines, share controls, related-topic
lists, or navigation text.

## 1. Crawl scope

- Allowed hosts: `bbc.com`, `bbc.co.uk`, and their subdomains.
- Seed page: `www.bbc.co.uk/business` (redirects to `/news/business`, depth 0).
- Only `http` and `https` links are eligible.
- Strip URL fragments; strip query strings from accepted article URLs.
- Ignore static files and duplicate URLs.
- Check `robots.txt` before every fetch, using the cached rules for each host.

## 2. Article URL rules

Accept a URL as a text article when its path matches either format:

- Current BBC: `/(section/...)/articles/<8-20 lowercase letters or digits>`,
  for example `/news/articles/c8vgyzn2d31yo`.
- Legacy BBC News: `/news/<slug>-<at least 5 digits>` with an optional `.html`
  suffix, for example `/news/world-europe-5122661.html`.

Article patterns are used to select the article-body extraction strategy, not to
reject every other page. Topic, section, and live-text pages remain eligible.

Always reject media and utility routes, including `/news/av`,
`/news/in_pictures`, `/news/videos`, `/video`, `/videos`, `/reel`, `/audio`,
`/sounds`, `/iplayer`, `/programmes`, `/newsletters`, `/search`, `/ugc`,
`/userinfo`, `/rss`, and `/feeds`.

## 3. Page classification

- Article: the URL matches section 2. As a fallback for redirected or changed
  URLs, require both BBC `headline-block` and `layout-block` components.
- Topic/index: any other accepted HTML page. Do not classify a page as an
  article merely because it contains `<article>` tags; BBC topic cards use them.

## 4. Article extraction

- Title: `headline-block h1`, then the first `h1`, `<title>`, or `og:title`.
- Body: paragraphs inside BBC `layout-block` components, preserving document
  order. Keep non-empty paragraph text of at least 10 characters and remove
  exact duplicates.
- Before extraction, remove `figure`, `figcaption`, `picture`, video/audio,
  iframes, scripts/styles, asides, captions, ad components, byline components,
  share controls, and tag/related-topic components.
- Store paragraphs separated by a blank line.

## 5. Topic extraction and discovery

- Page title: `<title>` with `og:title`/`h1` fallback.
- Stored content: unique modern `card-headline`/`card-description` pairs or
  BBC.co.uk `promo` headline/description pairs, when the enclosing link is not a
  media/utility route.
- Frontier links: normalized, in-domain links from `<main>`. With
  `ARTICLES_ONLY = False`, articles and useful topic/index pages are followed;
  media and utility routes remain excluded.
- Unknown-layout fallback: visible text from `<main>` after removing navigation,
  media/captions, ads, scripts, and styles.

## 6. Limits

The operational limits remain in `config.py`: `MAX_DEPTH = 3`,
`MAX_PAGES = 100`, `REQUEST_TIMEOUT = 10`, and `CRAWL_DELAY = 1.0` second.

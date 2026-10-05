# Selectors verified against the saved HTML

Both samples contain rendered DOM but no JSON-LD post records or ordinary
caption/user objects in their application/json scripts. Those scripts mostly
contain application bootstrap/configuration data. The parser therefore uses the
rendered cards rather than depending on an undocumented private API.

- Record: `[data-pressable-container="true"]`, excluding enclosing wrappers
  with nested pressable cards.
- Individual post scope: `[data-pagelet^="threads_post_page"]`.
- Search scope: `[data-pagelet^="threads_search_results"]`. The downloaded search
  file also contains `threads_feed_*` pagelets; those are excluded.
- Identity: `a[href]` wrapping `time`, URL path
  `/@<handle>/post/<shortcode>`. Query strings and `/media` suffixes are removed.
- Publication time: `time[datetime]` inside the same card.
- Content: `span[dir="auto"][style*="line-clamp"]` with direct plain child spans
  that carry the authored text. Exclude link/button ancestors, timestamps,
  styled child spans, and descendant UI controls. Join separate body paragraphs
  with newlines. The base-line-clamp variable alone does not prove truncation.
- Likes: `[role="button"]` containing `svg title` whose text is `Like` or
  `Unlike`, followed by the displayed counter. The saved post file has indentation
  even inside the SVG title, so normalize whitespace before matching.
- Grouping: shared ancestor `[data-virtualized]`. Preserve its first shortcode
  as `reply_group_id`; do not infer precise parentage from ordering or mentions.

The supplied example is comment `DHKOKsfSu0F`, author `_progamer_2133`, timestamp
`2025-03-14T00:30:39Z`, displayed likes `3`, in post `DHH7cJyP-aZ`.

These selectors are observed DOM conventions, not a stable platform API. The
tests deliberately remove all opaque CSS classes and verify text still parses.
Changes to semantic attributes or text wrappers may require a parser update.
Missing search/post sections raise `ParseError`; media-only or unsupported
comments are skipped with a warning. Nonempty partial pages can still be
incomplete, which is why every run records unknown coverage.


## Guest-search snapshots (October 5, 2026)

`fixtures/threads/guest_no_results.html` retains the actual `No results.` UI node
from the failed `namkiki` search. It has no search pagelets or post cards. That is
an explicit empty search, not evidence of a selector failure.
`fixtures/threads/guest_search_results.html` retains a rendered pagelet from the
`pbvm` search and its `Log in for more threads about this topic.` message. These
records are available but guest search coverage is limited. Fixtures retain only
the relevant DOM, excluding bootstrap scripts and other page assets.

Browser readiness waits for cards inside the requested panel, explicit empty
results, or an access/login challenge. A timeout still saves the page for
inspection. Empty results, login walls and unknown/missing DOM stay distinct.

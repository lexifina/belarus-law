# How this repository was made (Belarus)

Source: ETALON-ONLINE (https://etalonline.by/), National Centre of Legislation and Legal Research of the Republic of
Belarus. For each act, `https://etalonline.by/document/?regnum=<regnum>` gives the text in force and the list of
editions (`#versionList`: the day each edition applies from and the register number of the amending act). Each edition
is `?regnum=<regnum>&q_id=&date=<YYYY-MM-DD>&rnList=<amending regnum>&history=0` (`date=original` for the original
text). Only pages shown without registration are read. Fetching follows the site's robots.txt (Crawl-delay: 5): one
request at a time, 5 seconds apart, backing off on 429/5xx and stopping on 403.

`tools/build_etalon.py` fetches every edition, keeps the article text (headings, table of contents, editorial notes and
the signature are dropped), and appends one commit per edition with `git fast-import`. No model writes or alters legal
text; the code is deterministic. The scripts were written by Claude Code under Lexifina's direction.

Held back: future editions (not yet in force). No OCR: every text is HTML.

An earlier first build (30 October 2026, current texts from pravo.by only, no dated history) was never published; this
build replaces it and the placeholder.

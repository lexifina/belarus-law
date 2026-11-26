# Structure (Belarus)

Names are transliterated Russian, the language people search Belarusian law in.

- `konstitutsiya/`: `preambula.md`, `statya-001.md` ... (Конституция Республики Беларусь 1994 года)
- `kodeksy/<code>/statya-NNNN.md`: one file per article, e.g. `kodeksy/grazhdanskiy-kodeks/statya-0001.md`.
  Superscript articles: `statya-0046-1.md` (Статья 46¹). Dotted numbers (КоАП 2021, Статья 10.1): `statya-010-001.md`.
  One folder per code: grazhdanskiy-kodeks, ugolovnyy-kodeks, ugolovno-protsessualnyy-kodeks, trudovoy-kodeks,
  kodeks-grazhdanskogo-sudoproizvodstva, kodeks-ob-administrativnykh-pravonarusheniyakh, nalogovyy-kodeks-obshchaya-chast,
  nalogovyy-kodeks-osobennaya-chast, kodeks-o-brake-i-seme, zhilishchnyy-kodeks and the others.
- `zakony/<year>/<adopted>-<number>/statya-NNN.md`: laws in force, e.g. `zakony/2008/2008-10-28-433-z/` (Закон от
  28 октября 2008 г. № 433-З), with `preambula.md` where there is one.
- `dekrety/<year>/<adopted>-<number>/`, `ukazy/<year>/<adopted>-<number>/`: decrees and edicts of the President in
  force. An act with no articles is one file, `tekst.md`.
- Order of the build: the Constitution, the codes, then laws, decrees and edicts in force as ETALON-ONLINE lists them.

Each file: `# Статья N` on the first line, the article title on the second, then one paragraph per line.

Commits: one per edition, dated 12:00 Europe/Minsk on the day the edition applies from. Author: the amending act
(`Закон от 17.10.2025 № 100-З <h12500100@pravo.by.invalid>`; the e-mail is its register number); the original text is
authored by the act itself. Trailers: `Kind`, `In-force`, `In-force-basis`, `Source`, `Act-path`, `Edition`,
`Amending-act`. Editions that change no word of the text get no commit. Future editions are left out until in force.
Acts are appended one after another, so commit dates are in order within an act, not across the whole log.

corpus.json: `"corpus": "by/national/acts"`.

# Belarus: law history in git

**[Русский](README.md)** · **English**

The law of the Republic of Belarus as a git history: one file per article, one commit per edition (редакция) on the day it took effect, and the act that made the change (law, decree, edict or referendum decision) as the commit's author. Part of [lexifina/global-law](https://github.com/lexifina/global-law) (`by/`).

**What is in it now:** the Constitution and the codes of Belarus, each with every edition ETALON-ONLINE shows openly, from the original text to the edition in force. Codes are being added one by one, then the laws, decrees and presidential edicts in force (`zakony/`, `dekrety/`, `ukazy/`). See [STRUCTURE.md](STRUCTURE.md) and [REPRODUCE.md](REPRODUCE.md).

## Questions as git commands

| Question | Command |
| --- | --- |
| Every change to Article 23 of the Constitution | `git log -p -- konstitutsiya/statya-023.md` |
| Which act wrote each line of Civil Code art. 1? | `git blame kodeksy/grazhdanskiy-kodeks/statya-0001.md` |
| Criminal Code editions with their in-force days | `git log --format="%(trailers:key=In-force,valueonly,separator=) %an" -- kodeksy/ugolovnyy-kodeks` |

## Dates and authors

Each commit is dated noon (Europe/Minsk) on the day the edition applies from, as ETALON-ONLINE's list of editions gives it; trailers `In-force:`, `In-force-basis:`, `Source:`. The original text is dated to the day the act was adopted (its in-force day is not given in the list of editions). Future editions are not added before their in-force day.

The text is the control text of the ETALON data bank, not the official publication. Not legal advice.

Licence: [LICENSE](LICENSE) (Lexifina's work is CC0; legal acts are not objects of copyright, Law No. 262-З, art. 8).

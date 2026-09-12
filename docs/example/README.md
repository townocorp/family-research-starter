# A date that does not quite fit

**Entirely fictional. No real people, records or family projects were used.**
Person P001, Person P002, Place A and Place B are invented placeholders, not
pseudonyms for a public figure or a private family.

Person P001 remembers moving with Person P002 in 1912. A fictional school
register places P002 at Place B in 1911. The useful result is not a winning date.
It is a narrower claim, a visible contradiction and a sensible next question.

Read the [report draft](report.md) on GitHub, or download the
[self-contained HTML preview](report.html) and open it locally. GitHub normally
shows HTML source rather than rendering it. The commands below create the same
report as both Word DOCX and HTML. No hosting or upload is needed.

## What the example shows

- **First-hand recollection:** an invented speaker's memory, attributed rather
  than silently treated as proof.
- **Source statement:** what the invented register actually says.
- **Inference:** why an earlier residence is plausible but a permanent move date
  remains unresolved, with supporting and opposing evidence named.
- **Round closure:** a completed scoped negative, deferred work, a proposed
  correction and a lead. See the [round record](round-001.md).

The two [source](memory.txt) [texts](register.txt) were created as fiction on
2026-09-12. Their metadata uses that creation date, not the dates inside the
imagined story. The proposed 1950 recollection and 1911 entry are not historical
documents or transcripts of real recordings. Capture dates record the actual
local capture; update them if you reproduce this on a later date.

The report is deliberately text-only. It demonstrates attribution and reasoning,
not photographs, OCR, archive access, layout certification or a complete tree.
Everything in this example is covered by the starter's [MIT licence](../../LICENSE).
None of its assessments belongs in a real family's facts ledger.

## Reproduce the pair

Run from the starter checkout after its [local dependency setup](../tools.md).
Choose a **new, separate folder** with an existing parent. Do not use a real
research project for this demonstration. The initializer refuses existing
destinations and never creates a Git repository.

```powershell
.\.venv\Scripts\python.exe tools\starter.py init ..\fictional-example --owner P001 --canon markdown --skills
```

Stop if that command fails. With the new folder created, copy only these named
fictional inputs. These commands assume the exact destination chosen above:

```powershell
Copy-Item docs\example\memory.txt ..\fictional-example\originals\stories\E001.txt
Copy-Item docs\example\register.txt ..\fictional-example\originals\stories\E002.txt
Copy-Item docs\example\capture-memory.json ..\fictional-example\evidence\E001.json
Copy-Item docs\example\capture-register.json ..\fictional-example\evidence\E002.json
Copy-Item docs\example\report.md ..\fictional-example\reports\drafts\example.md
Copy-Item docs\example\round-001.md ..\fictional-example\research\rounds\round-001.md
```

Review the two metadata files and update `captured` to today's date. Run from the
starter checkout, using its explicitly installed dependencies. There is no
global configuration or hidden project discovery:

```powershell
.\.venv\Scripts\python.exe tools\starter.py capture --project ..\fictional-example --file ..\fictional-example\originals\stories\E001.txt --metadata ..\fictional-example\evidence\E001.json
.\.venv\Scripts\python.exe tools\starter.py capture --project ..\fictional-example --file ..\fictional-example\originals\stories\E002.txt --metadata ..\fictional-example\evidence\E002.json
.\.venv\Scripts\python.exe tools\starter.py check --project ..\fictional-example
.\.venv\Scripts\python.exe tools\starter.py report --project ..\fictional-example --draft reports\drafts\example.md --output reports\releases\example
```

Stop on any error. The outputs are `reports\releases\example.docx` and
`reports\releases\example.html` inside the new folder. Existing outputs are
refused. If you later work from that folder independently, install its own local
dependencies as described in the setup guide.

The round record is an example of proposed decisions, not an instruction to
approve facts. Neither the capture commands nor report generation changes the
canonical facts ledger.

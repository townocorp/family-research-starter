# Evidence capture and provenance

Capture is deliberately **local-file only**. Select the file and metadata
yourself. The tool neither downloads a URL nor reads a genealogy database.
Use local filesystems only. UNC, device-namespace, URI, symlink/reparse and
multiply-hardlinked regular-file inputs are refused before reading. A mounted
or mapped remote filesystem can look like a local path; verify the selected
storage yourself. Lexical path checks are not a network-isolation mechanism.

```powershell
.\.venv\Scripts\python.exe tools\starter.py capture --project . --file "<selected local file>" --metadata "<capture metadata JSON>"
.\.venv\Scripts\python.exe tools\starter.py catalogue --project .
.\.venv\Scripts\python.exe tools\starter.py check --project .
```

The metadata template is `evidence/capture-template.json`. Replace all
`REPLACE_` markers, choose the IDs and enter a real capture date before running.
Unknown source dates may be `unknown` or a four-digit year; do not invent dates.

Required metadata covers stable evidence ID, source type/date/locator, capture
date, custody, rights, consent, stated claim, first-hand/source/inference basis,
assessment, rationale, person IDs, round, supporting/opposing evidence and
summary. `url` is optional HTTP(S) without embedded credentials; do not record
private login URLs, session parameters or access tokens.

Person IDs use `P001`-style identifiers; evidence IDs use `E001`-style identifiers.
Related evidence must already be captured, except that a source may support its
own narrowly stated claim. A document saying something is not proof that the
thing happened. One source can support one claim and contradict another: record
those as separate assessments rather than assigning conflicting roles within
one claim. Use the correction ledger for subsequent reassessment.

`Supported` requires supporting evidence and rationale. `Unassessed`, `Tentative`
and `Disputed` also require rationale. These are human-readable assessments of
the stated claim, not whole-person labels, calibrated probabilities or model
votes. Opposing sources must not be omitted simply to make a story consistent.

Each capture creates `evidence/captures/E001/source.ext` and `record.md`, with
SHA-256, byte length, original filename, integrity/decoding scope and the supplied
provenance. The sidecar's flat YAML frontmatter uses JSON scalar/list syntax;
unsupported or duplicate fields are errors. Keep managed capture folders free
of extra files. Research notes and corrections belong outside them.

Supplied PNG/JPEG images are decoded completely. Supplied PDFs have their
structure and page streams checked, not their historical content or visual
legibility. Other formats are preserved and hashed with an explicit
**not decoded** assessment. No originals are rewritten or converted.

## Supplied OCR/transcript excerpts

If you supply a UTF-8 transcript/OCR derivative, add this `transcript` object to
metadata. Paths are explicit and project-relative:

```json
{
  "transcript": {
    "file": "derived/transcripts/E001.txt",
    "method": "human transcription",
    "author": "P001",
    "source_locator": "recording 00:10-00:14",
    "start": 0,
    "end": 11,
    "quote": "Person P001"
  }
}
```

This fragment is illustrative, not a complete capture record. `start` is an
inclusive Unicode-character offset and `end` is exclusive in the exact decoded
text, including any BOM and CR/LF characters. The quote must equal that span.
The tool stores the unchanged transcript bytes and their hash, method/author
and locator alongside the source. No whitespace or punctuation is normalised
for source-span checks. It does not perform or certify OCR.

## No-clobber and failure semantics

Identical capture bytes and metadata at the same evidence ID are a no-op.
Different bytes or metadata are refused. Use a new evidence ID and record the
old/new relationship in `research/corrections.md`; do not edit managed source
bytes. A single `.prev` file is not an archival revision history.

The catalogue is a regenerable inventory, separate from curated notes and the
canonical store. A missing source, changed hash, malformed metadata, linked path
or incomplete scan fails explicitly and leaves the previous catalogue intact.
If capture was saved but catalogue generation fails, the command says so and
returns nonzero; the captured evidence is retained for inspection.

Use one writer at a time. These local protections are not filesystem access
controls, backup software or a defence against a hostile concurrent writer.
Retain independent backups and review canonical-store changes separately.

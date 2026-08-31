# Notion → Attio, without the copy-paste

**Short version:** Maya's sheet says 7 of 8 rows are ready to go. Four of them have broken domains and one would quietly create a duplicate company. Fix the matching and the typing takes care of itself.

Here's a script reading their actual export, showing what the sheet thinks versus what should happen:

```
  8 rows in

     CONTACT        SHEET   PIPELINE  WHY
  ----------------------------------------------------------------------
   ! Priya Nair     READY   create    domain fixed (northbeam.example.com/ -> ...)
   ! Helena Costa   READY   create    domain fixed (oriel.example.com/uk -> ...)
   ! Amina Yusuf    CHECK   HOLD      no email, and email is Attio's key for people
   ! Lewis Grant    READY   create    band fixed (11–50 -> 11-50)
   ! Marta Silva    READY   attach    same company as Lewis Grant, no 2nd deal
     Emily Stone    READY   create    clean
     Soren Dahl     READY   create    clean
   ! Noor Hassan    READY   create    domain fixed (lattice.example.com/ -> ...)

  companies : 7   (one per domain)
  deals     : 7   (one per company, not per person)
  people    : 7
  held      : 1
```

That's the whole result, so there's nothing you need to run. If you want to check it, `python3 handoff.py` works with no arguments and no dependencies against the sample CSV in this repo. Nothing is sent anywhere. It writes four files: companies, people, deals, and a review queue.

---

## How I got there

I opened the CSV before I opened anything else. Eight rows is small enough to just read.

The obvious thing jumps out straight away. Brightyard appears twice, Lewis Grant and Marta Silva, same company. Marta's own research note says it in plain words: treat her as a second contact at the existing account, not a second opportunity. Amina Yusuf has no email, which is why she's the one row Maya flags. That much any pair of eyes catches in about a minute.

What I couldn't see was *why* the sheet doesn't catch Brightyard, given it's sitting right there. So I asked Claude to run the sheet's formulas against the rows properly rather than eyeballing them. Two things came back that I'd have missed for a long time.

**The trailing slash.** The domain formula is `SUBSTITUTE(SUBSTITUTE(website,"https://",""),"www.","")`. It strips the scheme and the www, but nothing else. One Brightyard row is `https://brightyard.example.com`, the other is `https://www.brightyard.example.com/`. After the formula, one ends in a slash and the other doesn't, so they're two different companies as far as the sheet is concerned. Same problem hits Northbeam, Oriel and Lattice Forge. Four of eight domains come out malformed, and nobody notices because Maya is reading the company name off the screen and searching Attio by hand anyway. The domain column is quietly wrong and a human is quietly compensating.

**The dashes.** This is the one I genuinely could not have found by looking. Employee ranges arrive as `51–200` on some rows and `51-200` on others. One is an en dash, one is a hyphen. On screen they are indistinguishable. To Attio they're two different values in a select field, so the same range slowly becomes several options, and every filter and report built on it gets a little less true. It's the kind of thing that never gets reported as a bug, it just makes the CRM feel vaguely unreliable a year later.

The last one isn't in the sample data so much as missing from it. Notion has `CRM company ID` and `CRM person ID` columns and they're empty on every row, and the working sheet has no column that would ever fill them. So the process has no way of knowing what it already did. Run the same batch twice and it duplicates rather than updates.

And on Amina: Maya's instinct is right and worth keeping. Email is Attio's unique key for people, so with no email there's genuinely nothing safe to match or create on. The script holds that row for exactly the reason she does.

## The point

The slow part isn't typing. It's deciding whether a record already exists, and being careful because the process can't be safely repeated. Fix matching and give it a memory, and the typing disappears on its own.

## Ways to improve it

**Keep the spreadsheet, drop the typing.** Run the script, take its output CSVs, import them with Attio's *Update existing* option mapped on Domains and Email. That's an upsert, so duplicates stop happening. Maya handles the one held row. No engineering needed.

**Drop the spreadsheet too.** Same rules, pulling from the Notion API instead of a CSV, writing via Attio's upsert endpoint (`PUT /v2/objects/{object}/records` with a `matching_attribute`), then writing record IDs back into Notion and flipping the status. Run it twice, nothing changes.

**Drop the batch.** Notion fires on status change, there's no weekly ritual at all, and Maya works a short exception list instead of a queue.

An LLM earns its place only at the fuzzy edges: awkward names, deciding whether *Alder & Finch* and *Alder and Finch Ltd* are the same company, drafting the meeting note from the research notes. The model suggests, the rules decide.

## Assumptions

- Notion API token with write access. Read-only still works, but the write-back stays manual and the memory problem stays.
- Attio API key, or a user who can run CSV imports.
- Permission to add one custom field for the Notion `Source ID`. My only schema request, and it's what makes re-runs safe.
- Qualified accounts is an Attio list.
- Existing Attio data may already contain duplicates, so matching has to handle multiple candidates, not just zero or one.
- Unclear whether there's a Zapier/Make budget or a preference for owned code. The three options above exist so that can be decided later.

## With more time

- **A real working demo.** With more time I could have shown this actually running rather than described it. The script here stops at a dry run; wiring it to the Notion and Attio APIs is a small step, and with Claude helping it's a few hours of work, not days.
- Time the current process properly. I've assumed matching is the bottleneck from watching the video; a stopwatch would confirm it.
- Test the matcher against past batches where the answer is already known, and count how often it agrees.
- Dedupe what's already in Attio first, so automation doesn't inherit the mess.
- Validate the website field at entry in Notion, which removes this class of problem upstream.

## AI use

I used Claude throughout, and I'm happy to say so.

Reading the file myself gave me the obvious things: Brightyard turning up twice, the missing email. Claude went deeper and found the trailing slash and the two different dash characters, which I don't think I'd have spotted on my own. It also checked Attio's current documentation so I wasn't relying on memory.

The models are good enough now that work like this comes together quickly. Deciding what to look at first, and which findings actually mattered, still felt like the useful part. It's how I'd expect to work on the job.

---

[Attio unique identifiers](https://attio.com/help/reference/attio-101/introduction-to-data-importing) · [bulk update via CSV](https://attio.com/help/reference/imports-exports/csv-imports/bulk-update-records-via-csv-import) · [upsert endpoint](https://docs.attio.com/rest-api/endpoint-reference/records/upsert-a-record)

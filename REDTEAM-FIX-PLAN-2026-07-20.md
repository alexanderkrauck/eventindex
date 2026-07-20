# Red-Team Fix Plan (audit 2026-07-20, 14-event stratified sample)

Findings: 3 confirmed defects, 1 confirmed incompleteness, 2 relevance/
provenance issues, 2 suspects. Every fix below is generic - no per-site code.
Order: forensics before mechanism (two root causes are hypotheses until the
claims/venues tables confirm them).

## P0 - immediate, cheap, no code (needs go)

- **QA-check the flagged occurrences now**: enqueue `qa_check` for the
  Wochentagsmesse-Tuesday, Flohmarkt, Stahlwelt, AEC-Highlightführung,
  Nierenstammtisch occurrences (cents; the designed tool for exactly this).
- **Audit-intake agent sessions**: enqueue `agent_extract` for meinbezirk
  (venue+detail-URL misses) and argeniere (event moved to /wels) - same
  user-reported-miss intake as factory300.

## P1 - the confirmed-defect mechanisms

1. **Weekday-suffixed series merge (Wochentagsmesse "- Freitag" on a
   Tuesday).** Forensic step first: confirm normalize_title strips the
   weekday so all five Mo-Fr masses share one fingerprint and identity
   merges them (the 2026-07-13 (title,venue) tradeoff firing wrongly).
   Fix: weekday words (Mo..So, Montag..Sonntag) become identity-bearing in
   normalize_title - five masses = five events, each on its correct
   weekday. "Yoga am Montag" vs "Yoga am Mittwoch" split correctly too.
   Fingerprint shift is precedented (identity union keeps lineage); gold
   set gates the merge; the next canon rebuild heals prod history
   automatically. Regression test: weekday-titled event => >=60% of its
   occurrences on that weekday; plus a digest metric counting violations
   (the watched number).
2. **Announcement non-events (Stahlwelt "Wiedereröffnung - Touren ab...").**
   (a) llm_text prompt gains a negative example: reopening/offer
   announcements ("Wiedereröffnung", "jetzt wieder geöffnet", "Touren ab
   <Datum>", "neue Öffnungszeiten") are NOT events unless a specific dated
   celebration is described ("Wiedereröffnungsfeier am..." IS one).
   (b) _NON_EVENT_RE gains the unambiguous patterns (wiedereröffnung/
   neueröffnung WITHOUT feier/fest). Both run in sanity_filter AND
   _load_claims, so the immutable history is healed at the next rebuild -
   no backfill script. Fixture test from the live Stahlwelt text.
3. **QA loop v2** (four upgrades that turn nightly QA into the drift-catcher
   the audit shows it must be):
   (a) verdict prompt requires venue/time consistency when the page shows
       them (the Flohmarkt class: a list page must not "confirm" a market
       at the wrong Interspar with the wrong hours);
   (b) headless fallback: before ruling not_found on a page whose static
       text lacks the title, render once (AEC "Mehr Termine" class - no
       LLM cost, one Playwright render);
   (c) sampling gains a projected-occurrence share (2-8 weeks out):
       projections are currently never verified, which is how the parish's
       "neue Gottesdienstzeiten ab 20.09." and summer-paused dance classes
       drift silently;
   (d) a not_found streak (>=3 in one run, per source) enqueues
       agent_extract with the findings as reason (cooldown-guarded) - the
       Nierenstammtisch class heals itself by the agent finding /wels.

## P2 - merge-precision hardening (gold-set gated)

4. **Chain-brand venue guard (Flohmarkt class).** Forensic step first: pull
   the claims/venue rows behind the merged market. Fix: when two venue
   names share their leading brand token but the remainders are non-empty
   and dissimilar ("Interspar Wegscheid" / "Interspar Industriezeile"),
   never auto-merge - adjudicate with address/geo evidence. Generic rule,
   no brand list.
5. **Generic-title merge guard.** Events whose normalized title has <=2
   meaningful words ("Flohmarkt", "Vereinsabend") require venue agreement
   (venue_id equality or tight geo) for identity merge, not just the
   geo-cell. Precision@merge >=0.98 stays the gate.
6. **Escalation fuses reset by audit findings.** completeness_escalated /
   venue_escalated are one-shot flags; a parity-audit coverage miss on the
   same source clears them so the contracts can re-fire (meinbezirk class:
   the venue contract fired once historically and can never fire again).
7. **Holiday-projection labeling (Cooper Dance class).** Occurrences that
   are projected AND fall in a school-holiday window (holidays table
   exists, H1.2) get an exposed `holiday_uncertain` flag + a confidence
   haircut at serve time - label, never suppress (null-semantics
   conform). Consuming LLMs see the uncertainty.

## P3 - needs your decision (Class C flavor)

8. **Foreign-place geo enrichment (Crikvenica class).** Enrichment already
   runs per event; add: when the only location evidence is a place name in
   the text, geocode it via the existing Google Places key and set event
   geo - the serve-time geo gate then filters foreign events naturally.
   Conforms to "index generously, filter at serve time" (adds knowledge,
   suppresses nothing), but it changes serve outcomes and adds ~cents of
   Places spend: y/n?
9. **Exhibition range semantics (Schlossmuseum class).** Prompt rule:
   Ausstellungen extract as (opening date -> closing date) ranges, served
   by the locked overlap semantics; never a synthetic mid-run date. Low
   risk, listed here only because it touches extraction semantics broadly.

## Verification

- Each fix ships with a regression test derived from the audit case
  (fixture text from the live pages where feasible).
- Gold set + fixture replays gate 1, 4, 5 (merge-precision changes).
- Acceptance: rerun this exact stratified 14-sample audit protocol after
  deploy; target zero confirmed class-1..3 defects on a fresh sample, and
  the healed prod rows for the known cases (rebuild heals 1+2 history;
  venue split for the Flohmarkt case may need one curated-venue chat fix,
  as precedented).
- Costs: everything rides existing budget rings; QA headless adds render
  time only; P3.8 adds marginal Places spend.

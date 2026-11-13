# Rahnuma — Viva Notes

## 1. How this project meets the requirements

| Requirement | Where it appears |
|---|---|
| **Inferencing** | Our own forward-chaining engine `engine/inference.py`: agenda (conflict set), conflict resolution, refraction, cycle cap and MYCIN certainty factors. Report section **"How the system reached this"** lists every rule firing. |
| **Diagnosis** | Rule groups G1–G4 work like a doctor: answers (symptoms) → aptitude profile and eligibility gaps (diagnosis) → fields (treatment). Report section **"Diagnosis"**. |
| **Decision making** | G8 makes the final decisions: top 3 fields with confidence words, "Insufficient data" (DS06), strict not-eligible verdicts (G4) and university filtering (G7). |
| **Decision support system** | The student decides; the system supports: university table with filters (including "Show only verified"), job outlook with sources, action plan (RC06), alternatives (RC07), and the **"What if?"** panel that re-runs the engine on changed answers. |
| **Minimum 50 conditions** | 90 rules (55 compute, 35 decision) with 209 leaf conditions. Shown on the **Knowledge Base** page, worked out from `rules.json`. |
| **Unique niche** | Field and university advice for Pakistani students using PMDC, PEC, HEC, PNMC and PCATP rules and MDCAT / LAT / ECAT. |
| **Streamlit UI on WAN** | Streamlit only, deployed on Streamlit Community Cloud (URL in README and on the About page). |

Pages: **Students → Guided Counselling** (step-by-step consultation and diagnosis), **Students → Counsellor Desk**
(quick diagnosis on one screen, 5 sample students), **Experts → Knowledge Base**, **Experts → Knowledge Acquisition**, **About**.

## 2. The six expert-system components

| Component | File(s) | One-line explanation |
|---|---|---|
| Knowledge base | `knowledge_base/*.json`, `kb_loader.py` | Rules, thresholds, questions, fields, universities and market data, all as data. |
| Working memory | `engine/working_memory.py` | A dictionary of `Fact(name, value, cf, source_rules)` for one consultation. |
| Inference engine | `engine/inference.py`, `conditions.py`, `actions.py` | Forward chaining: match → conflict resolution → fire → repeat. |
| Explanation facility | `engine/explanation.py` | "Why are you asking?", the plain-English trace and the reasons on each field. |
| Knowledge acquisition | `views/knowledge_acquisition.py` | Experts edit thresholds and data, the order checks run, then "Apply for this session". |
| User interface | `app.py`, `views/`, `ui/` | Streamlit pages. No logic here: the pages call `run_consultation()`. |

`engine/` and `knowledge_base/` never import Streamlit, so all logic is tested with pytest.

## 3. Rule groups

| Group | Priority | What it does |
|---|---|---|
| G0 Data sufficiency (DS01–DS06) | 100 / 99 | Missing essentials → "Insufficient data" and HALT. |
| G1 Sanity checks (SC01–SC05) | 90 | Odd inputs → warning; wrong-stream or out-of-range scores are ignored (the value stays visible in the warning, e.g. "MDCAT 70 ignored because your stream is ICS"). |
| G2 Derived facts (DF01–DF08) | 80 | Marks band, MDCAT pass marks, marks reliable. |
| G3 Aptitude profiling (AP01–AP14) | 70 | Interests + skills → aptitudes with CFs. |
| G4 Eligibility (EL01–EL19) | 60 / 59 | Strict admission rules → eligible / conditional / not eligible. |
| G5 Field match (FM01–FM19) | 50 | Eligibility + aptitudes → suitability CF per field. |
| G6 Job market (MK01–MK03) | 40 | Extra evidence for high demand (schema rules). |
| G7 University matching (UN01–UN08) | 30 / 29 | Candidate universities, filters, relaxation (schema rules). |
| G8 Final recommendation (RC01–RC08) | 20 … 13 | Top 3, advice, action plan, alternatives, summary. |

## 4. Forward chaining, with a worked example (Hamza)

Forward chaining starts from the facts (the answers) and fires every rule whose IF part is true,
adding new facts, until nothing more can fire. Each cycle:

1. **Match**: find rules (and schema-rule instances) whose conditions are true and that have not fired.
2. **Conflict resolution**: pick one by (1) higher priority, (2) more leaf conditions, (3) smaller rule ID.
3. **Act**: fire it, record a trace step, and start the next cycle.

Hamza: Pre-Engineering, Inter 76%, likes Maths and computers, Not sure about electronics, good at problem solving, likes teamwork, wants abroad.

| Cycle | Rule fired | Conflict set at that level | CF calculation | New fact |
|---|---|---|---|---|
| 1 | DF02 | DF02, DF08 | 1 × min(1) = 1.0 | inter_band = Good |
| 2 | DF08 | DF08 | 1 × min(1) = 1.0 | marks_reliable |
| 3 | AP01 | AP01, AP04, AP03 | 0.9 × min(1, 1) = 0.9 | apt_analytical |
| 4 | AP04 | AP04, AP03 | 0.85 × min(0.5, 1) = 0.425 | apt_electrical (Not sure halves it) |
| 5 | AP03 | AP03 | 0.9 × min(1) = 0.9 | apt_computing |
| 6 | EL08 | EL08, EL10, EL12, EL16, EL13 … | 1 × min(1, 1, 1) | EE, ME, Civil eligible |
| 7 | EL10 | EL10, EL12 … | 1 × min(1, 1, 1) | CS, SE eligible |
| 8 | EL12 | EL12, EL16 … | 1 × min(1, 1, 1) | Architecture eligible |
| … | FM01 | FM01, FM03, FM04 | 0.9 × min(1, 0.9, 0.9) = 0.81 | suit.cs = 0.81 |
| … | MK02[cs] | MK02[cs], MK02[se], MK01[cs] … | 0.15 × min(1) | suit.cs: 0.81 combined with 0.15 → 0.839 |
| … | MK01[cs] | MK01[cs], MK01[se] … | 0.2 | suit.cs: 0.839 combined with 0.2 → 0.871 |
| … | RC01 | RC01 | — | Recommendation #1 = CS (Very likely) |

Notes on the example:
- Cycle 1: DF02 and DF08 have the same priority (80) and the same number of conditions (1), so the smaller ID wins.
- Cycle 3: AP01 and AP04 (2 conditions) beat AP03 (1 condition): specificity.
- EE gets suit 0.85 × 0.425 = 0.361, below `min_show_cf` (0.4), so it is not recommended.

## 5. Conflict resolution, refraction and the cycle cap

- **Order**: higher priority → more leaf conditions (specificity) → smaller rule ID. Exclusive conclusions get different priorities (RC01 = 20, RC02 = 19, RC03 = 18 …) so they never depend on a tie-breaker.
- **Refraction**: each rule fires once; each schema instance such as `MK01[cs]` also fires once. This stops loops: a rule whose THEN keeps its own IF true still fires only once (tested in `tests/test_engine.py`).
- **Cycle cap**: `max_cycles` (500) from `thresholds.json`. If it is hit, the engine stops and records a warning (tested with a cap of 3).

### Why checking from the highest priority level down gives the same result

The engine sorts rules by priority once, then in each cycle evaluates them from the highest priority level down
and stops after the first level that has at least one matching rule. This is only a speed-up; it gives exactly
the same rule firing order as building the full conflict set:

1. Priority is the **first** sort key in conflict resolution, so any matching rule at a lower level would always lose to a matching rule at the higher level. It can never be picked in this cycle.
2. Checking a condition does not change working memory, so skipping the lower levels changes no facts.
3. Inside the chosen level every rule is still checked, so specificity and rule-ID tie-breaks are applied exactly as before.
4. The next cycle starts again from the top, so a lower-priority rule fires as soon as nothing above it matches.

## 6. Certainty factors (MYCIN)

- Conclusion CF = rule CF × min(CF of the matched facts). Example: AP04 = 0.85 × min(0.5, 1) = 0.425.
- Two agreeing pieces of evidence for the same fact: CF1 + CF2 × (1 − CF1). Example: 0.6 and 0.5 → 0.6 + 0.5 × 0.4 = 0.8. Hamza CS: 0.81 → 0.839 (abroad demand) → 0.871 (Pakistan demand).
- No negative CFs: "low job demand" is a note (MK03), not negative evidence.
- Words: ≥ 0.8 Very likely, ≥ 0.6 Likely, ≥ 0.4 Possible; below 0.4 not shown.
- FM02 (CS with computing but no analytical aptitude) has `NOT apt_analytical`, so FM01 and FM02 never count the same evidence twice.

## 7. "Not sure" answers

Yes = CF 1.0, Not sure = `notsure_cf` (0.5), No = no fact. So a Yes-rule still fires on Not sure, at half confidence.
Every Yes / No / Not sure question starts with no answer selected, and the wizard does not move on until it is answered.

## 8. Data sufficiency: blank vs 0

G0 rules have the highest priority. A blank field is missing; 0 is real data. Empty input → "Insufficient data" with the list
of what is missing, and DS06 HALTs the engine. Inter % = 0 is not missing: the band is "Very low" and no field is eligible.

## 9. Strict eligibility vs conditional

- A not-eligible field never gets a suitability fact (FM rules require eligible or conditional), so it can never be recommended.
  A property-style test runs 150 random answer sets to check this.
- "Eligible" only when every qualification fact has CF 1.0. If one is uncertain (Not sure about Physics, or Part-I marks with CF 0.8),
  the status becomes **conditional**, CF = min(`conditional_cf` 0.7, fact CFs), with a reason such as "confirm that you studied Physics".
- When two rules set the same field, the better status wins (eligible beats conditional) and the reasons are merged.
  "Not eligible" comes only from EL18 or EL19, and nothing can upgrade it.
- **Architecture threshold:** `arch_min` = 45 and all six streams are allowed. The field rule means "at least one university accepts you"
  (NCA accepts 45% and IVS has no stream rule); UN02 then applies each university's own minimum (for example UET Lahore and NED need 60%).

## 10. Schema rules

A schema rule has `"for_each": "field"` and runs once per field (18 instances), but it counts as one rule.
The trace shows instances like `MK01[cs]`. Used in G6 (MK01–MK03), G7 (UN01–UN08), EL19 and RC07.

## 11. University matching (G7)

UN01 lists universities offering the field (women's universities are left out for male students), tagged "test taken / not yet".
UN02 removes offerings below their minimum % (strict, never relaxed). UN03 removes only offerings whose **known** fee band is above
the budget; unknown fees stay, tagged "Fee not confirmed — check with the university", after the confirmed ones. UN04–UN07 apply
city, hostel, women-only and sector. If nothing is left, UN08 relaxes city first, then budget, and says what it relaxed.

## 12. Knowledge sources (as of 2026-11-13)

- PMDC (60% HSSC Pre-Medical; MDCAT 55% MBBS / 50% BDS), PNMC (BSN 50%), HEC LAT (50/100), PEC rules as applied by university pages,
  PCATP "Accreditation Status of Educational Institutions" (July 2026).
- University admission and fee pages; 76 of 234 offerings verified on an official page. Each threshold lists its source in `thresholds.json`.
- Job market: SBP, PBS, Bureau of Emigration & Overseas Employment and news reports; estimates are labelled "estimate".

## 13. Limitations

The rules simplify real admission policies; merit cut-offs change every year; university data may change and many rows could not be
verified online; the job-market data is broad and partly estimated.

## 14. Likely viva questions

1. **Why forward chaining and not backward chaining?** We start from the student's answers and want every conclusion they lead to (all eligible fields, all suitable fields, universities). That is data-driven, so forward chaining fits. Backward chaining suits proving one goal.
2. **Why not use experta or another rule library?** The teacher wanted us to show inferencing. Writing the engine ourselves shows the agenda, conflict resolution, refraction and CF maths clearly, and avoids an old, unmaintained library.
3. **What happens if two rules conclude the same thing?** The CFs combine with MYCIN: CF1 + CF2 × (1 − CF1). For eligibility, the better status wins instead.
4. **How does conflict resolution work?** Priority first, then more conditions, then the smaller rule ID.
5. **What is refraction?** A rule (or schema instance) fires only once. It prevents infinite loops.
6. **What if a rule keeps matching forever?** Refraction stops it; the cycle cap (500) is a second safety net.
7. **What is a certainty factor?** A number from 0 to 1 showing how strongly we believe a fact.
8. **How is a conclusion's CF calculated?** Rule CF × the smallest CF among the matched facts.
9. **Why min and not average?** A chain is as strong as its weakest link; one uncertain answer should limit the conclusion.
10. **What does "Not sure" do?** It adds the fact with CF 0.5, so Yes-rules fire at half confidence.
11. **What if the student leaves everything blank?** G0 rules list what is missing and DS06 halts: "Insufficient data".
12. **Is 0% treated as missing?** No. 0 is real data: band Very low, nothing eligible.
13. **Can a not-eligible field ever be recommended?** No. FM rules need eligible or conditional status, and a random test checks it.
14. **What is "conditional"?** Eligible only if something is done or confirmed, e.g. pass MDCAT or HEC LAT, confirm Physics, or wait for final marks.
15. **How do you add a new rule?** Add an entry to `rules.json` (ID, group, priority, CF, type, if, then, text), using `@key` for numbers. Run `pytest`; tests check unique IDs and threshold keys.
16. **How would you add a new field?** Add it to `fields.json` and `market_data.json`, add an eligibility rule (EL) and a field-match rule (FM), and add university offerings. Schema rules pick it up automatically.
17. **What if PMDC changes the MDCAT pass mark?** Change `mdcat_pass_mbbs` in `thresholds.json` (or on the Knowledge Acquisition page). No code changes.
18. **Why are numbers in thresholds.json and not in the rules?** So experts can update policy values in one place and see their sources. A test scans the rules for number literals.
19. **What is a schema rule?** One rule written once and applied to each field, e.g. MK01[cs], MK01[se]. It counts as one rule.
20. **How does the system explain itself?** "Why are you asking?" is built from each rule's `asks` list; "How the system reached this" turns each trace step into a sentence; technical mode shows rule IDs and CF sums.
21. **Where is diagnosis in this project?** G1–G4: answers → sanity checks → marks band and aptitudes → eligibility gaps, shown in the Diagnosis section.
22. **Where is decision support?** University filters, job outlook, action plan, alternatives and the What-if panel. The student makes the final choice.
23. **How does What-if work?** It copies the answers, changes a few, runs the engine again and compares fields, CFs and university counts. Saved answers change only if the student presses "Use these answers".
24. **Why does the engine stop checking at the first priority level with a match?** Lower levels would always lose on priority, and checking does not change facts, so the result is identical. It is just faster.
25. **Why is the architecture minimum 45%?** It means at least one accredited university (NCA) accepts 45%; UN02 enforces each university's own minimum.
26. **Why do some universities show "Fee not confirmed"?** The official fee could not be read; we keep them so the student can check, but list them after confirmed ones.
27. **How do you know the data is correct?** Each offering has a source URL and a `verified` flag; only offerings read on an official page on 2026-11-13 are marked verified (76 of 234).
28. **What are the limitations?** Simplified policies, yearly merit changes, partly unverified university data and estimated market data.
29. **How is the knowledge acquisition safe?** Edits are checked (band order, MDCAT marks, CF ranges, budgets) and refused with a plain message if wrong; changes apply only to the session.
30. **How is the project tested?** 50 pytest tests: CF maths, rule format, conflict resolution, refraction, cap, blank vs 0, random eligibility checks, the 5 sample students, What-if cases, data files and an end-to-end wizard run.


YOU HAVE FULL AND COMPLETE READ AND WRITE ACCESS TO THE REPO FROM MY OTHER ACCOUNT BECAUSE I HAVE ADDED YOU AS A GROUP MEMEBER WITH A DEVELOPER ROLE:

https://gitlab.com/scrap-group/scrap-project

SO IT MEANS YOU CAN EXAMINE FILES, MODIFY, CREATE AND IMPLEMENT, COMMIT AND CREATE MERGE REQUEST ETC

CRITICAL: EVERYTHING IS ON THE MAIN BRANCH. 

DO NOT FOOLSIHLY START LISTING WHAT IS ON THE MASTER BRANCH

HERE IS EXACTLY WHAT I WANT YOU TO DO:

NOW WE ARE GOING TO WORK ON THIS TEST CODEBASE GIVEN TO ME.

THE CURRENT CODEBASE IS EXACTLY WHAT I HAVE DONE

THERE ARE OVER 200+ PARTICIPANT AND MY GOAL TO ACHIEVE 1ST POSITION AND NOTHING LESS THAN 1ST POSITION.
SO AS A SENIOR BACKEND ENGINEER WITH CCOMBINED EXPERTISE ON SCRAPING, AUTOMATION, OPTIMIZATION, CODE QUALITY, SCALABILITY ETC YOU ARE GOING TO WORK WITH ME TO ACHIEVE THIS .

REQUIREMENTS AND INSTRUCTIONS GIVEN IS AT THE /rules/

DATA GIVEN ONLY IS AT THE /data/. 


THE PROBLEM NOW IS THAT WHEN I RUN IT HANGS, TIMESOUT AND RETURNS NO LISTING. BUT THE ORIGINAL CODEBASE WAS TAKING JUST 3 MINUUTES MAX TO COMPLETE AND RETURNS ABOUT 300+ LISTINGS


I WANT YOU  TO EXAMINE THE ENTIRE CODEBASE DEEPLY AND THOROUGHLY TO FIGURE OUT THE ISSUE AND ADDRESS IT.

AVOID PATCH WORK

AVOID GUESSING

AVOID ASSUMPTIONS

WE ARE TALKING ABOUT REAL ENGINEERING HERE NOT JOKES.

AND THE MAIN FOCUS IS ON RUNTIME SPEED, ACCURCACY AND SCALABILITY




The output files in the repo are from a **stale, broken run**, not the most recent ones. They show:

#### Current state of `output/` in the repo

- **`listings_consolidated.csv`** — header only, **zero listings**.
- **`error_log.csv`** — 30 rows, mostly `site_not_reachable`. Missing 8 of the 38 input domains entirely (no entry for `zelidom.fr`, `erafrance.com`, `erapontdelarc.com`, `vancia-immobilier.fr`, `novilis.fr`, `piriac-immobilier.fr`, `wretmanestate.com` is duplicated as success/failed, etc.).
- **`domain_status_summary.csv`** — same 30 rows, all failed. Includes the broken-state durations: `groupimmo.pro 618.73s`, `grisel-immobilier.fr 618.71s`, `agencemathieu.fr 399.66s`, `lgo-immobilier.fr 399.61s` — these are the cascade-broken values from the original `_default_executor` hijack failure mode, **before any of our fixes**.

#### Accuracy verdict on what's currently in the repo

**Inaccurate and misleading.** Specifically:

1. **Zero listings written** despite the input having ~30+ scrapeable domains. This output is from a run where the 359-listing CSV got truncated by a subsequent failed `--reset-checkpoint` run that crashed before writing anything.

2. **Wrong reasons.** Every domain marked `site_not_reachable` — but in your real runs, sites like `rhpatrimoine.com`, `maxihome.net`, `nestenn.com`, `agencecoullaud.fr` are **definitely reachable** (we've seen them produce 14, 30+, 30+, 24+ listings). The "site_not_reachable" tag came from the head-of-line cascade misclassifying timeouts as unreachability. The pipeline already classifies timeouts as `no_listings_found`, but this old run predates that fix.

3. **Wrong durations.** 618s on `groupimmo.pro`/`grisel-immobilier.fr` is the original `_default_executor` deadlock; current code can't produce that value because every path is now wall-clock-bounded.

4. **Missing rows.** Only 30 of 38 input domains are present. The truncated CSV indicates the run was `^C`'d before all domains finished, and the `summary.record` writes per-domain at completion only.

5. **Inconsistency with what we know works.** Your last successful run produced 359 listings across roughly 18 successful domains. None of that is reflected in the repo output.

#### What this means for accuracy evaluation

The output files in the repo are **not a fair sample** to judge accuracy on. They predate every fix from MR !18 onward. We have ~zero on-disk evidence to evaluate field-level accuracy (price extraction quality, dedup behavior, location parsing, etc.) because the listings file is empty.

To actually evaluate accuracy of resolvers (price, surface_area, rooms, location, coordinates, dpe_rating), we need a **clean run committed to the repo**. The 359-listing run from your terminal output produced real data, but it's on your local disk, not in git.

#### What I recommend

Once you decide on Option A / B / C from my previous message, run the scraper, then commit the resulting `output/*.csv` files. Then I can do a proper field-by-field accuracy audit: per-domain success rate, per-field fill rate, dedup effectiveness, suspicious values (e.g., €0 prices, 0,0 coordinates, malformed phones), and overall data shape.

Right now there is nothing in the repo to audit.
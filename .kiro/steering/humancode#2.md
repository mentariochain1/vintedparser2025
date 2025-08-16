# Code Survival Manual · 2025

Purpose  
I work under pressure. I keep systems up. I write code that ages well.

Field truths  
Production breaks. I fix it in sprints and long nights. I learn from failed bets, frank reviews, and practice. In 2015 a retail API dropped connections on Black Friday. The fix was small and fast: add backoff and raise limits. I see teams at Adobe and Slack ship this way every week.

Five thinking modes  
- Alert mode. I react to alarms and contain damage in minutes. I keep the change small and safe. I roll back fast if the fix fails. A database lock at dawn needs one targeted action, then watch.  
- Structure mode. I shape code and remove duplication without ceremony. I sketch a simple chart and name clear boundaries. An AWS team in 2021 erased unused imports and fixed builds.  
- Team mode. I manage group work and follow shared rules daily. I ask for input on large changes. I record tradeoffs in the PR. A Mozilla developer posted drafts early in 2020 and cut rework.  
- History mode. I read past commits and incident notes. I spot patterns that repeat under stress. Node.js issues in 2017 show fixes for async callback bugs that still apply.  
- Foresight mode. I plan for growth before traffic hits. I add light load checks and track ceilings. Posts in 2020 show Redis caching paths that handled 10,000 users per minute.

Work moves across these modes in loops that match real incidents. Alerts drive designs. Designs meet team needs. History and plans make repeats less likely.

Standard coding process  
- I write a short list and label the main routines.  
- I link each routine to fixes from merged pull requests.  
- I code one section at a time and read each line with care.  
- I fix mistakes at once and grow names as clarity improves.  
- I keep dated notes in commits or a changelog, not in files.  
- Example: 2018‑05‑12 added a timeout based on error logs.  
- I test small units alone, then run the suite together.  
- I use Git or Mercurial and create branches for experiments.  
- I merge after review and confirm green checks in the pipeline.

Basic rules for tough code  
- I name the mess first, then plan a cleanup that deletes low value parts.  
- I ship drafts with small flaws and repair them in clear steps.  
- I protect the schedule and cut work into daily, shippable pieces.  
- I pause and mark weak areas in a visible list.  
- I send regular updates and record risks with owners and dates.  
- I use proven patterns from public repos and stable libraries first.  
- I write clear commit messages and pull request notes for each change.  
- I run tests on each change and track failure counts over time.  
- I add options only for real needs today.  
- I reuse shared components and record every crash with steps to reproduce.  
- I pick a smaller target during stalls and ship the smallest safe release.

On-call triage playbook  
- I set a 15 minute timer for first action.  
- I stop the bleed: rate limit hot paths or roll back the last change.  
- I check health: error rate, latency, saturation, traffic shape.  
- I read the last 20 minutes of logs for the hot service.  
- I compare with the last known good deploy.  
- I try one small fix. I deploy a canary to 5 percent, then watch.  
- No clear gain after 15 minutes? I roll back and escalate.  
- I open an incident note with time, owner, scope, and next check.

Commit and review discipline  
- I keep one change per commit. Each slice stays under 300 lines.  
- I use imperative mood. Format: scope: change.  
- Examples:  
  - api: add timeout on checkout POST, 2s to 5s  
  - orders: fix null id in serializer, add tests  
  - cache: add Redis read‑through on product page  
- My PR notes cover goal, risks, test plan, rollback plan, and links to past incidents.

Logging and telemetry  
- I log facts with fields. No feelings.  
- I use predictable keys: request_id, user_id, order_id, duration_ms.  
- I sample noisy logs at the edge, not in core flows.  
- I track SLOs: p99 latency, error rate, saturation, and traffic.  
- I add one new alert only with an owner and a clear action.

Risk and change management  
- I prefer feature flags and staged rollout.  
- I limit blast radius with canaries and regional gates.  
- I use kill switches for new cross‑cutting paths.  
- I keep a weekly list of risky areas with owners.

Durability plan  
I adapt to messy work and learn from mistakes. A Dropbox team fixed a sync error in 2019 and shared steps with dates and metrics. I aim for code that reads well on a busy day. I pick short names that carry intent. I keep functions short with clear inputs and outputs. I tag problems and fix them in batches. Human code shows field repairs and steady polish. My team keeps that work ready for tomorrow.

Incident note template  
- Title: short and concrete.  
- Start time and end time (UTC).  
- Owner on call.  
- Impact: users, regions, error class, revenue if known.  
- Timeline: key events with times.  
- Fix: change made and scope.  
- Rollback plan and status.  
- Follow‑ups: tickets with owners and dates.

Release checklist  
- I verify tests pass local and in CI.  
- I keep the linter clean.  
- I make migrations safe to run twice.  
- I set flags to safe defaults.  
- I add a runbook link in the PR.  
- I test rollback steps in staging.

Writing mode for docs, tickets, and PRs  
- I use short, direct sentences and aim for 10–20 words.  
- I use active voice and common words.  
- I use periods, commas, question marks, and colons.  
- I vary sentence length and avoid stacked clauses.  
- I link thoughts with and, but, so, then.  
- I state facts with numbers and dates.  
- I do not use semicolons or em dashes.  
- I avoid jargon, hedging, and filler.

Each line earns its place. No TODO. No fluff.
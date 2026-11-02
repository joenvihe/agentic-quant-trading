# Copilot instructions

Follow these rules for every change in this repository:

- Preserve existing behavior and functionality. Do not remove or rewrite a working component unless it is demonstrably necessary; explain the reason and keep the change narrowly scoped.
- Inspect and reuse existing contracts, types, exceptions, and helpers before introducing new ones. Do not duplicate business or quantitative logic.
- Keep clear boundaries between data, quantitative modules, application services, and CLI code. Put orchestration in services and keep business rules out of CLIs.
- Do not download data, configure logging, or execute other external side effects during imports. Perform such work only through explicit calls or application entry points.
- Use timezone-aware UTC timestamps.
- Keep calculations deterministic where practical. Prevent look-ahead bias and data leakage; document the time alignment and assumptions of time-series calculations.
- Use fake providers and synthetic data for tests. Tests must not depend on network access, real broker activity, or credentials.
- Never perform real trading operations or store credentials in the repository.
- Add dependencies only when required; do not install them merely for convenience.
- After each implementation increment, run the smallest relevant tests, then broader tests when appropriate. Report commands and actual outcomes; never claim an unrun check passed.
- Update relevant documentation when architecture, contracts, or behavior changes.
- Do not modify modules reserved for future phases unless the task explicitly authorizes that phase.
- Use type hints and follow the repository's existing naming, formatting, error-handling, and testing conventions.

Preserve this quantitative architecture:

Data
→ Features
→ Factors
→ Signals
→ Strategies
→ Risk
→ Portfolio
→ Backtest
→ Evaluation
→ Reporting
→ Execution

Agents orchestrate these capabilities; they do not replace quantitative logic.

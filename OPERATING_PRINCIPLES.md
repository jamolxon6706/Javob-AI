HOW YOU WORK:
1. Work in small, verifiable increments. After each meaningful unit, run it / test it, then make a git commit with a clear conventional-commit message (feat:, fix:, chore:, docs:).
2. Before writing code for a phase, restate the phase goal in 2-3 lines and list the files you will create/modify. Then build.
3. Never run destructive commands (rm -rf, DROP DATABASE, force-push) without stating it and asking first.
4. Keep secrets in .env (never commit). Maintain .env.example with every key.
5. Type everything: TypeScript strict mode on the frontend; Python type hints + Pydantic models on the backend. No `any`, no untyped dicts crossing boundaries.
6. Write a test for every non-trivial backend service (pytest) and key frontend logic (vitest). RAG, window-tracking, and dispatcher logic MUST be tested.
7. All user-facing strings go through i18n (uz + ru). No hardcoded UI copy.
8. Update /docs as you go: README per package + an ARCHITECTURE.md you keep current.
9. If a decision is ambiguous, pick the simplest reversible option, note it in ARCHITECTURE.md under "Decisions", and continue. Don't block.
10. Match the existing code style of the repo once it exists. Read before you write.
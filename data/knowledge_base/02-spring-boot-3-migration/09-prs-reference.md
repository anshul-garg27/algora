# Key PRs Reference - Spring Boot 3 Migration (gh Verified)

---

## Migration PRs

| PR# | Title | +/- Lines | Files | Merged | Role |
|-----|-------|-----------|-------|--------|------|
| **#1176** | Spring boot 3 migration initial | +1,766/-1,699 | 151 | Mar 7, 2025 | Initial groundwork |
| **#1312** | Feature/springboot 3 migration | +1,732/-1,858 | **158** | Apr 21, 2025 | **THE MAIN PR** |
| **#1337** | Feature/springboot 3 migration (Release) | +1,795/-1,892 | 159 | Apr 30, 2025 | Production release |

## Immediate Post-Migration (Wave 1: Week 1)

| PR# | Title | +/- Lines | Merged | What Fixed |
|-----|-------|-----------|--------|-----------|
| **#1332** | snyk issues + mutable list | +48/-36 | Apr 23 | Snyk CVEs + List.of() |
| **#1335** | sonar issue fixed | +1/-1 | Apr 23 | Code quality |

## Ongoing Post-Migration (Waves 2-7)

| PR# | Title | +/- Lines | Merged | What Fixed |
|-----|-------|-----------|--------|-----------|
| **#1394** | snyk fixes + Spring Boot 3.3.12 | +6/-5 | Jun 3 | Version bump for security |
| **#1425** | GTP BOM 2.2.1 | +515/-838 | Aug 11 | Internal platform alignment |
| **#1498** | GTP BOM issue fix | +19/-42 | Sep 22 | ObservabilityServiceProvider |
| **#1501** | GTP BOM prod changes | +542/-884 | Sep 23 | Production GTP alignment |
| **#1528** | Heap OOM fix + postgres | +224/-66 | Oct 6 | Memory leak, try-with-resources |
| **#1527** | Correlation ID fix | +34/-16 | Oct 6 | Filter chain propagation |
| **#1564** | Downstream API timeout | +573/-35 | Nov 4 | WebClient retry + backoff |
| **#1594** | Startup probe fix | +31/-11 | Jan 6 | K8s actuator health |

---

## Timeline

```
Mar 7, 2025   │ PR #1176: Initial migration groundwork (151 files)
              │
Apr 21        │ PR #1312: MAIN migration PR (158 files) ← THE BIG ONE
Apr 23        │ PR #1332: Snyk + mutable list fix
Apr 23        │ PR #1335: Sonar fix
Apr 30        │ PR #1337: Released to production ← GO LIVE
              │
Jun 3         │ PR #1394: Bumped to Spring Boot 3.3.12 (security)
              │
Aug 11        │ PR #1425: GTP BOM 2.2.1 (+515/-838) ← MAJOR
              │
Sep 22-23     │ PR #1498, #1501: ObservabilityServiceProvider migration
              │
Oct 6         │ PR #1528: Heap OOM fix (try-with-resources)
Oct 6         │ PR #1527: Correlation ID propagation fix
              │
Nov 4         │ PR #1564: WebClient timeout + retry logic (+573) ← IMPORTANT
              │
Jan 6, 2026   │ PR #1594: K8s startup probe fix
              │
              │ Migration truly "done" ~9 months after initial PR
```

---

## Top 5 PRs to Memorize

| # | PR# | One-Line Summary |
|---|-----|------------------|
| 1 | **#1312** | Main migration: 158 files, javax→jakarta, WebClient, CompletableFuture |
| 2 | **#1564** | WebClient timeout + retry with exponential backoff (573 lines) |
| 3 | **#1528** | Heap OOM fix - try-with-resources for resource management |
| 4 | **#1425** | GTP BOM 2.2.1 alignment (515 additions, 838 deletions) |
| 5 | **#1332** | Immediate post-migration: Snyk CVEs + List.of() immutability |

---

## Statistics

| Stat | Value |
|------|-------|
| Main migration PR | #1312 (158 files, +1,732/-1,858) |
| Post-migration fix PRs | 10 PRs over 9 months |
| Total lines changed (post-migration) | ~2,000+ additions |
| Repo total PRs | 1,600+ |

---

## Commands

```bash
export GH_HOST=gecgithub01.walmart.com

gh pr view 1312 --repo dsi-dataventures-luminate/cp-nrti-apis
gh pr view 1564 --repo dsi-dataventures-luminate/cp-nrti-apis
gh pr view 1528 --repo dsi-dataventures-luminate/cp-nrti-apis
```

---

*The story: migration PR in April → 9 months of production hardening → truly done in January 2026.*

---
name: commit-review
description: Review of the staged changes before a commit in this repo — derives which docs must move from WHAT is staged (a new module, config, task script or test; a snapshot name delta; a changed count; new user-facing behaviour) instead of from a plan's doc list, separates code findings into fix-now vs defer, then runs the two mechanical gates.
triggers:
  - review uncommitted changes
  - review the staged changes
  - before commit
  - commit review
  - are the docs updated
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(grep:*), Bash(bash bin/check_doc_drift.sh:*), Bash(bash bin/check_snapshot_staged.sh:*)
metadata:
  audience: developers
  workflow: commit
---

# Commit review — the checklist is derived from the diff, not from the plan

Why this exists (2026-09-28): a feature commit updated every doc its plan named and still left five
copies stale — two module inventories, the unit-test map's prose copy, an "all modules untested"
claim and the known-differences table. A plan's *Docs* column is the minimum, never the list.
What a script can decide is in `bin/check_doc_drift.sh` (run by the commit gate); what needs
judgement is the table below.

## 1. What is staged

    git status --short && git diff --cached --stat

Everything under review must be staged; unstaged edits are not part of the commit. Read the whole
diff of code and config; read the doc diffs for the numbers and names they change.

## 2. Derive the docs from the change type

| Staged | Must move with it | How to check |
|---|---|---|
| new / removed dir under `modules/local/` or `subworkflows/local/`; new / removed `conf/**/*.config` or `.yml` | its row in the matching ADDED table of `docs/dev-practices/SAREK_MODIFICATIONS.md`, and the heading + Summary counts | `bash bin/check_doc_drift.sh` |
| new `bin/` script that a module calls | it is a behaviour path (the gate derives the set from `modules/**/main.nf`); a TESTMAP entry in `bin/check_snapshot_staged.sh` if it has a test | drift script |
| new `tests/*.nf.test` | the gate's TESTMAP (process / workflow tests); the §11 layer table in `docs/dev-practices/testing_best_practices.md`; any prose the test makes false | drift script, then `grep -rn -E 'untested|no automated test|not tested' docs CLAUDE.md` |
| `tests/ottilie_e2e.nf.test.snap` gains or loses output names | a dated row in `docs/dev-practices/output_comparison.md` §2.10; the output tree in `README.md` if a new `<outdir>` folder appears | gate rule 1; read the `.snap` diff as source code |
| a count changed anywhere (tasks, processes, files, modules, test cases) | every copy of the OLD value — the number and its prose phrasings (CLAUDE.md §13: a corrected number has copies) | `grep -rn -E '\b<old>\b' CLAUDE.md README.md CHANGELOG.md docs` |
| new user-facing behaviour or parameter | `README.md`, `CHANGELOG.md`, a `docs/README.md` index row for a new doc, the CLAUDE.md summary AND its linked doc (maintenance convention), the schema help text, the launch-form overlay | read them |
| a new `[yAMP …]` console line | the zero-lines invariant of `tests/preflight.nf.test` on the ottilie profile | run it |
| anything under `workflows/` or `subworkflows/` | `tests/qc_gate.sh a` (the starvation gate) | trailer demanded by the gate |

Two rules behind the table. A measured number lives in ONE dated place (the CHANGELOG entry) and
other docs point there rather than copy it. A list that copies the tree is either deleted in favour
of a pointer or turned into a table the drift script parses.

## 3. Code findings: fix now or defer

Any edit to a behaviour path (module, config, workflow, task script) after the cited validation runs
invalidates them — the commit message's e2e / module-test / gate claims would become false. For each
finding say which it is: **fix now** (tooling, docs, a script the gate does not treat as behaviour)
or **defer** to the next commit that touches that file, with the re-validation cost stated. A
cosmetic finding on a failure-only path is normally deferred.

## 4. Run the gates on the drafted message

    bash bin/check_doc_drift.sh
    bash bin/check_snapshot_staged.sh <path-to-drafted-message>

Both must exit 0. A `DRIFT:` line names its fix; a `BLOCKED:` line names the missing trailer or file.
Note for Claude Code sessions: the PreToolUse hook blocks any Bash command whose text contains
`git commit`, including a heredoc that merely mentions it — write such files with the Write tool.

## 5. Report

Verdict first (code sound or not; docs complete or which are stale), then the stale docs as a list
with `file:line`, then the code findings tagged fix-now / defer, then the validation each claim rests
on (the runs the message cites, with dates). Commit only validated work; no plan artefacts (work
package letters, plan-file names) in committed code, config or comments.

# Azure provisioning scripts

Infrastructure-as-scripts for running yAMP on **Azure Batch via Seqera Platform**. Everything here is
tracked in git so that *what was granted, to whom, and when* is reviewable. Nothing here runs as part
of the pipeline — these are one-shot operator scripts.

Pipeline-facing counterparts: [`docs/seqera_cloud/`](../../docs/seqera_cloud/) (design + checklist) and
[`docs/dev-practices/azure_batch_execution.md`](../../docs/dev-practices/azure_batch_execution.md)
(execution gotchas found by running it).

## Governing rule: least privilege, per-resource scope

**Every role assignment is scoped to a single resource — never to the resource group, never to the
subscription.** `rg-ALEdb` holds unrelated Batch accounts (`anp`, `ale`, `aledevyeast`,
`seqeracomputebatch`) and unrelated storage accounts; an RG-wide grant hands the pipeline SP all of
them. That was the mistake corrected once already in `tmp/azure/azure_sp/04_remove_old_sp.sh` — do not
reintroduce it.

Target grants for the Seqera SP:

| Scope (exact resource) | Role | Why this role |
|---|---|---|
| Batch account `aledev4test` | `Azure Batch Data Contributor` | Create/manage pools, jobs, tasks. Narrower than `Contributor`; per Seqera's Azure Batch docs it is sufficient. |
| Storage account `aledata` | `Storage Blob Data Contributor` | Read/write the Nextflow work dir. **Data-plane only** — cannot rotate keys, change network rules, or delete the account. |

Deliberately **not** granted: `Contributor` at any scope, anything on the subscription, anything on
`rg-ALEdb`, and any role on the other five Batch accounts or the other storage accounts.

Widen only on a demonstrated `AuthorizationFailed`, and then only by one step, at the **same resource
scope** — e.g. `Azure Batch Data Contributor` → `Contributor` *on the `aledev4test` Batch account*. Record
the failing operation in `RUNBOOK.md` before widening, so the reason survives.

Conditional, only if the situation actually arises (from the plan's Phase 1.2): `Managed Identity
Operator` per managed identity if pools use one; `Network Contributor` on the VNet if pools are placed
in a private VNet.

## Layout

| Path | Purpose |
|---|---|
| `seqera-sp/00_vars.sh` | Every account name / ID / scope as a shell variable. **No secrets.** Sourced by all other scripts. |
| `seqera-sp/NN_*.sh` | Numbered, run in order. The early scripts (01–05) alternate read-only checks and mutations; from 08 on the numbers are chronological only — read each script's header. (07 is a deliberate gap: the deploy-key script was deleted with its dead route.) |
| `seqera-sp/RUNBOOK.md` | The audit record: dated entry per script actually executed, with outcome. Committed. |
| `seqera-sp/logs/` | Raw `tee` transcripts. **Gitignored** — they can contain tokens. `RUNBOOK.md` is the committed summary. |

## Conventions

1. **Idempotent.** Re-running a script must be safe. `az role assignment create` is a no-op if the
   assignment already exists (warns, exit 0).
2. **Check before mutate.** Every mutating script is preceded by a read-only script that prints the
   current state. Read that output before running the next number.
3. **Scopes come from `00_vars.sh` only.** Never inline a scope string in a mutating script — that is
   how an RG-wide scope slips in unnoticed. `00_vars.sh` derives each scope from `az ... show --query id`
   so the resource is resolved, not typed.
4. **No secrets in this tree.** Not in scripts, not in `.env` files here. See below.
5. **Log every run:**
   ```bash
   ./NN_something.sh 2>&1 | tee "logs/NN_$(date -u +%Y%m%dT%H%M%SZ).log"
   ```
   Then add a one-line entry to `RUNBOOK.md`.

## Identifiers: names in, GUIDs derived

**No Azure GUID is hard-coded anywhere in this tree** — not the subscription, tenant, app, object, or
scope IDs. `seqera-sp/00_vars.sh` holds *resource names* and resolves every ID at runtime via `az`.

They are **not secrets** — you cannot authenticate with an app ID or a tenant ID; that needs the client
secret or a certificate, and the tenant ID is already publicly resolvable from the `dtu.dk` domain via
the OIDC discovery endpoint. The reasons to keep them out are different:

- **Reconnaissance value.** A file naming the subscription, the Batch account, the storage account and
  the exact SP authorized to write to them is a ready-made targeting package — which app to phish for
  consent, which storage account to probe for public containers, which SP secret is worth hunting.
  No single item is an exploit; together they lower an attacker's cost for free.
- **Permanence + trajectory.** Git history cannot be quietly walked back, and `CLAUDE.md` keeps the
  manifest in `org/repo` form specifically so open-sourcing stays viable.
- **Precedent.** Before this directory existed, the repo tracked **zero** Azure GUIDs. Committing them
  would start a habit rather than continue one.

Deriving at runtime also removes a class of drift: an SP recreated under the same name resolves
correctly, and a stale pasted GUID can no longer silently point at the wrong principal. `00_vars.sh`
fails loudly if a name matches zero or multiple principals, or if a scope resolves to anything broader
than a single resource.

Transcripts in `logs/` do print full GUIDs — which is why `logs/` is gitignored and `RUNBOOK.md` (the
committed record) refers to everything by name.

## Secret handling

The service principal's client secret is shown **once**, by `az ad app credential reset`. Policy:

- **Preferred:** paste it straight into the Seqera Platform credential form and never write it to disk.
- **If it must persist:** `~/.config/ale-seqera/sp.env`, `chmod 600`, **outside the repo**. Scripts here
  read it via `${AZURE_CLIENT_SECRET:-}` from the environment; they never write it.
- `deploy/azure/.gitignore` blocks `*.env` / `*.secret` / `logs/` as defence in depth, but the rule is
  "don't put it here", not "rely on the ignore file".
- Record the secret's **expiry date** in `RUNBOOK.md` — an unnoticed expiry is silent breakage months
  later.

## Migrating from `tmp/azure/`

`tmp/azure/azure_sp/` holds the earlier, untracked iteration of this work (and a plaintext
`.azure_sp.env`). Treat it as historical scratch: do not extend it. Anything still needed should be
rewritten here against `00_vars.sh`, and the plaintext secret in `tmp/azure/azure_sp/.azure_sp.env`
should be rotated out (`az ad app credential reset`) once the new credential is in place.

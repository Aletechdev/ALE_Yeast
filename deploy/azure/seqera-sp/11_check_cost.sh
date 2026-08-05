#!/usr/bin/env bash
# Actual Azure spend for the Batch account, by day and meter.
#
# ⚠️ Cost data lags 8-24h (sometimes 48h). A run finished today will show 0.00 —
# that means "not billed yet", NOT "free". Check again tomorrow.
#
# Azure Batch itself costs nothing; you pay for the pool VMs, their managed disks,
# and storage transactions. Those bill under the Batch account resource.
#
#   ./11_check_cost.sh          # last 14 days
#   DAYS=30 ./11_check_cost.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh >/dev/null

DAYS="${DAYS:-14}"
FROM=$(date -u -d "$DAYS days ago" +%Y-%m-%d)
TO=$(date -u +%Y-%m-%d)
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT

cat > "$TMP" <<JSON
{"type":"ActualCost","timeframe":"Custom",
 "timePeriod":{"from":"${FROM}T00:00:00+00:00","to":"${TO}T23:59:59+00:00"},
 "dataset":{"granularity":"Daily",
  "aggregation":{"totalCost":{"name":"Cost","function":"Sum"}},
  "grouping":[{"type":"Dimension","name":"ResourceId"},{"type":"Dimension","name":"Meter"}]}}
JSON

echo "Batch account: $BATCH_ACCOUNT   window: $FROM .. $TO"
az rest --method POST \
    --url "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$STORAGE_RG/providers/Microsoft.CostManagement/query?api-version=2023-03-01" \
    --body "@$TMP" --headers "Content-Type=application/json" -o json 2>/dev/null \
| ACCT="$BATCH_ACCOUNT" python -c "
import json,sys,os,collections
acct=os.environ['ACCT'].lower()
rows=json.load(sys.stdin)['properties']['rows']
meters=collections.defaultdict(float); days=collections.defaultdict(float); cur='?'
for cost,day,rid,meter,c in rows:
    cur=c
    if acct in rid.lower():
        meters[meter]+=cost; days[str(day)]+=cost
if not meters:
    print('  no billed usage yet for this account in the window.')
    print('  Cost data lags 8-24h — a run from today will not appear until tomorrow.')
    sys.exit()
print(f'  --- by meter ({cur}) ---')
for k,v in sorted(meters.items(), key=lambda x:-x[1]):
    print(f'    {k:34s} {v:9.2f}')
print(f'  --- by day ---')
for k in sorted(days): print(f'    {k}  {days[k]:9.2f}')
print(f'  TOTAL {sum(meters.values()):.2f} {cur}')
"

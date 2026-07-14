#!/usr/bin/env bash
# Build, test, and push the GENERATE_INDEX container to GitHub Container Registry (ghcr.io).
#
# Prerequisites (one-time):
#   - A GitHub account/org.
#   - A GitHub Personal Access Token (classic) with scope: write:packages
#       export GH_PAT=ghp_xxxxxxxx
#       export GH_USER=<your-github-username>
#   - Choose the target org/namespace:
#       export GH_ORG=<your-github-org-or-username>
#
# Usage:
#   GH_USER=... GH_ORG=... GH_PAT=... bash containers/generate_index/push.sh [tag]
#
# After pushing, pin the printed URL in:
#   modules/local/generate_index/main.nf   (container directive)
# and make the package Public in ghcr (Package settings) so runners can pull it.
set -euo pipefail

TAG="${1:-1.0.0}"
: "${GH_ORG:?set GH_ORG to your github org/username}"
: "${GH_USER:?set GH_USER to your github username}"
: "${GH_PAT:?set GH_PAT to a PAT with write:packages}"

IMAGE="ghcr.io/${GH_ORG}/ale-reports:${TAG}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ">> Building ${IMAGE}"
docker build -t "${IMAGE}" "${HERE}"

echo ">> Smoke-testing imports"
docker run --rm "${IMAGE}" python -c "import pandas, jinja2; print('OK', pandas.__version__, jinja2.__version__)"

echo ">> Logging in to ghcr.io"
echo "${GH_PAT}" | docker login ghcr.io -u "${GH_USER}" --password-stdin

echo ">> Pushing ${IMAGE}"
docker push "${IMAGE}"

echo ""
echo "Done. Pin this in modules/local/generate_index/main.nf:"
echo "    container '${IMAGE}'"
echo "Remember to set the ghcr package visibility to Public."

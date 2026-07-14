# Container for the GENERATE_INDEX process (docs/igvreports/generate_index.py).
# Sole runtime deps: pandas + jinja2. Kept intentionally minimal.
#
# Build & push (see push.sh):
#   docker build -t ghcr.io/<org>/ale-reports:<tag> containers/generate_index/
#   docker push  ghcr.io/<org>/ale-reports:<tag>
#
# Then pin the pushed URL in modules/local/generate_index/main.nf (container directive).
FROM python:3.12-slim

# procps provides `ps`, which Nextflow requires in every task container to collect
# runtime metrics (without it the task is marked failed). nf-core images bundle it too.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Pinned for reproducibility. Bump deliberately.
RUN pip install --no-cache-dir \
        pandas==2.2.3 \
        jinja2==3.1.4

# Sanity-check the imports at build time so a broken image fails the build.
RUN python -c "import pandas, jinja2; print('deps OK', pandas.__version__, jinja2.__version__)"

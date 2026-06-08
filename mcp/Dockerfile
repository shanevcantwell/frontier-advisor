FROM python:3.13-slim

# ── Node + the `claude` CLI (top advisory tier) ──────────────────────────────
# The top tier shells out to the `claude` CLI (@anthropic-ai/claude-code), which
# needs Node.js. We bundle ONLY the CLI binary here. No credentials are baked:
# OAuth creds are supplied at runtime via a read-only mount of the host's
# ~/.claude (see install.sh / README). Never add ARG/ENV/COPY for any API key
# or OAuth credential to this image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y npm \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ARCHITECTURE.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

# The `claude` CLI reads OAuth creds from $HOME/.claude/.credentials.json.
# Default the container HOME to a stable, mountable location. At `docker run`
# time the host's ~/.claude is mounted read-only here (see run instructions).
ENV HOME=/home/advisor
RUN mkdir -p /home/advisor

ENTRYPOINT ["frontier-advisor"]

# Runtime-specific paths are confined to deployment and wrappers.
FROM golang:1.26.2-bookworm@sha256:47ce5636e9936b2c5cbf708925578ef386b4f8872aec74a67bd13a627d242b19 AS tools
RUN CGO_ENABLED=0 go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@v0.0.2 \
 && CGO_ENABLED=0 go install github.com/xdevplatform/xurl@v1.1.0
FROM node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6 AS node
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && apt-get update && apt-get install -y --no-install-recommends git bash curl ca-certificates ripgrep \
 && rm -rf /var/lib/apt/lists/*
ARG CODEX_VERSION=0.157.1
RUN npm install -g @openai/codex@${CODEX_VERSION}
COPY --from=tools /go/bin/blogwatcher /usr/local/bin/blogwatcher-cli
COPY --from=tools /go/bin/xurl /usr/local/bin/xurl
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
 && pip install --no-cache-dir --no-deps . \
 && useradd -m -u 1000 wiki
ENV AI_TOPICS_CODEX_SOURCE=/app WIKI_PROFILE_ROOT=/workspace/profile \
    HOME=/workspace/profile WIKI_AGENT_HOME=/workspace/profile/.wiki-agent WIKI_SUBPROCESS_HOME=/workspace/profile \
    PATH=/app/bin:/usr/local/bin:/usr/bin:/bin \
    BLOGWATCHER_BIN=/usr/local/bin/blogwatcher-cli XURL_PATH=/usr/local/bin/xurl
USER wiki
ENTRYPOINT ["/app/bin/ai-topics-codex"]
CMD ["serve"]

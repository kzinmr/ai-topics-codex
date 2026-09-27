# Development contract

This repository is the Codex-native Lucy runtime. Codex App Server with ChatGPT
subscription authentication is the only model harness. Do not reintroduce an
adapter registry, an API-key fallback, legacy agent tools or legacy runtime state.

Paths: WIKI_PROFILE_ROOT → WIKI_SUBPROCESS_HOME → Path.home(); HOME is the dedicated
profile. Canonical content is ~/wiki, scripts ~/.wiki-agent/scripts, runtime state
~/.wiki-agent, Codex skills ~/.agents/skills, authentication CODEX_HOME (default
~/.codex). Change code, assets, deployment and migration docs together.

Keep content/feed definitions in ai-topics and operational code here. Never copy
credentials, native binaries, gateway history or private run artifacts into Git.
Use isolated profiles for tests. Do not run production collectors or notification
transports as incidental tests. Preserve live Lucy and Nana unless cutover is
explicitly requested. Import legacy state only through the versioned migration.

Validate with unittest, compileall, validate, check-skill-links and
check-public-tree. Test protocol failures and data integrity, not wording.
Native skills have required name/description frontmatter. Historical skill
session notes are evidence of migration decisions, not active instructions.

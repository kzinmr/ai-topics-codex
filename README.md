# ai-topics-codex

Lucy の AI 情報収集と Karpathy 型 LLM Wiki 管理を **Codex + ChatGPT サブスクリプション認証**で動かす実行基盤です。モデル処理は Codex App Server に統一しました。Hermes / pi のインストール、設定、スケジューラは不要です。

Wiki・原文・feed 定義は [ai-topics](https://github.com/kzinmr/ai-topics)、運用コード・30ジョブ・23スキル・移行ツールはこの repository が管理します。

- RSS / newsletter / X / sitemap → raw 保存 → triage JSON → Wiki統合 → index/log・品質チェック。
- 定時実行、依存段階の成功・鮮度検査、単一 writer lock、実行履歴、失敗復旧、独立した配信 outbox。
- ChatGPT 認証を実行前に確認。APIキー・別モデルプロバイダーへ自動で切り替えません。
- ホストまたは権限を制限した Docker で配備。旧状態は新しい形式へ明示的に変換します。

[Docker依存撤去の評価](docs/docker-free-assessment.md) · [調査・移植レポート](docs/migration-report.md) · [設計](docs/architecture.md) · [移行手順](docs/migration.md) · [運用](docs/operations.md) · [検証記録](docs/validation.md)

## ホストで始める

Linux/WSL、Python 3.12+、Git、Codex CLI が必要です。検証版は `codex-cli 0.157.1`。Windows は WSL または Docker を使います。この checkout と assets を保持して運用してください。

```sh
git clone https://github.com/kzinmr/ai-topics-codex.git
cd ai-topics-codex
uv sync --frozen --extra collectors
npm install -g @openai/codex@0.157.1
export WIKI_PROFILE_ROOT="$PWD/profiles/lucy"
bin/ai-topics-codex init --clone
bin/ai-topics-codex login
bin/ai-topics-codex account
bin/ai-topics-codex validate
bin/ai-topics-codex run blog-triage --dry-run
```

`login` は Codex の device authorization を起動します。ブラウザでの本人認証が必要です。使用枠・利用可能モデルは契約に依存します。サブスクリプション認証とAPIキー課金は別の方式です。[公式認証仕様](https://learn.chatgpt.com/docs/auth)

`init` は既存 profile を上書きしません。既存 Lucy のデータは [移行手順](docs/migration.md) で新しい profile に入れてください。`init` のみ（`--clone` なし）は空の試験領域を作ります。

設定は `$WIKI_PROFILE_ROOT/.wiki-agent/local.json`、収集・配送の認証情報は同じディレクトリの `secrets.json`。例は [local.example.json](config/local.example.json) と [secrets.example.json](config/secrets.example.json) です。APIキーはモデル実行には不要ですが、IMAP / X / Slack 等の取得元認証は別途必要です。

```sh
# RSS / X の CLI を destination 用にインストール（Go が必要）
tools/install-source-tools
bin/ai-topics-codex exec python3 "$WIKI_PROFILE_ROOT/.wiki-agent/scripts/import_opml.py"
bin/ai-topics-codex doctor
# 準備済み profile の最初の段階から明示的に実行
bin/ai-topics-codex run blog-ingest
bin/ai-topics-codex run blog-triage
bin/ai-topics-codex run blog-wiki-ingest
```

初期値は `publication: "local"`（編集のみ）とローカル outbox。実運用でコンテンツを commit/push する場合は Git 認証・作成者・hooks を確認して `publication` を `push` にします。これはモデルへの公開指示であり、Git操作をOSで禁止する機構ではありません。

## Docker

初回検証ではホストのsandbox起動失敗を回避するためDockerを使用しました。ただしDockerは必須ではなく、今後は標準sandboxによるホスト運用へ統一する方針です。このホストでは配布版bubblewrapと専用AppArmorプロファイルが未導入でした。原因候補・現行設計の不足・撤去条件は [再評価](docs/docker-free-assessment.md) を参照してください。以下は現在残っている [Docker 手順](docs/operations.md#docker) です。Compose は read-only root、非rootユーザー、capability削除と専用profile mountで隔離し、Codexには `externalSandbox` を指定します。ホストの標準動作は `workspace-write` のままです。

```sh
mkdir -p profiles/lucy
export LUCY_PROFILE_DIR="$PWD/profiles/lucy"
export WIKI_UID="$(id -u)" WIKI_GID="$(id -g)"
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm lucy init --clone
docker compose -f deploy/compose.yaml run --rm lucy login
docker compose -f deploy/compose.yaml run --rm lucy account
```

収集元・Git設定と `doctor` が通ったら `docker compose -f deploy/compose.yaml up -d`。旧 Lucy と同時に同じ Wiki を更新させないでください。Nana は移行対象外です。

## 検証

```sh
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src assets tools tests
bin/ai-topics-codex validate
uv run python tools/check-skill-links.py
uv run python tools/check-public-tree.py
docker compose -f deploy/compose.yaml config --quiet
```

実モデルのテストは `tools/smoke-codex.py --live --auth-home <認証ディレクトリ>`。隔離した合成Wikiで triage → JSON handoff → Wiki生成 → index/log と raw 不変性を検証します。実行にはサブスクリプション使用枠を使います。CI は実モデルや外部通知を呼びません。

# ai-topics-codex

Lucy の AI 情報収集と Karpathy 型 LLM Wiki 管理を **Codex + ChatGPT サブスクリプション認証**で動かす実行基盤です。モデル処理は Codex App Server に統一しました。Hermes / pi のインストール、設定、スケジューラは不要です。

Wiki・原文・feed 定義は [ai-topics](https://github.com/kzinmr/ai-topics)、運用コード・30ジョブ・23スキル・移行ツールはこの repository が管理します。

- RSS / newsletter / X / sitemap → raw 保存 → triage JSON → Wiki統合 → index/log・品質チェック。
- 定時実行、依存段階の成功・鮮度検査、単一 writer lock、実行履歴、失敗復旧、独立した配信 outbox。
- ChatGPT 認証を実行前に確認。APIキー・別モデルプロバイダーへ自動で切り替えません。
- Docker不要のホスト運用。Codex標準sandboxでWiki・管理コード・認証情報の権限を分離します。

[ネイティブ移行検証](docs/native-validation.md) · [Docker依存撤去の評価](docs/docker-free-assessment.md) · [調査・移植レポート](docs/migration-report.md) · [設計](docs/architecture.md) · [移行手順](docs/migration.md) · [運用](docs/operations.md) · [検証記録](docs/validation.md)

今後の検討: [OpenAIサービスによる周辺基盤の簡素化（設計ドラフト・未実装）](docs/openai-services-design-draft.md)。
責務の再分解: [通常ソフトウェア・モデル処理・Agent Harnessのモジュール設計（検討用・未実装）](docs/modular-wiki-design-draft.md)。
学習用の実行記録: [2026-09-30のドラフト検証とCodex SDK実験](docs/learning-lab-validation-2026-09-30.md)。

## ホストで始める

Linux/WSL、Python 3.12+、Git、Codex CLI が必要です。検証版は `codex-cli 0.157.1`。Windows は WSL2 を使います。Linuxではbubblewrapが必要です。この checkout と assets を保持して運用してください。

```sh
git clone https://github.com/kzinmr/ai-topics-codex.git
cd ai-topics-codex
uv sync --frozen --extra collectors
npm install -g @openai/codex@0.157.1
# Ubuntu 24.04では管理者が一度だけ実行（全体のAppArmor制限は維持）
sudo tools/setup-linux-sandbox
export WIKI_PROFILE_ROOT="$PWD/profiles/lucy"
bin/ai-topics-codex init --clone
bin/ai-topics-codex login
bin/ai-topics-codex account
bin/ai-topics-codex sandbox-check
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

初期値は `publication: "local"`（編集のみ）とローカル outbox。実運用でコンテンツを commit/push する場合は Git 認証・作成者・hooks を確認して `publication` を `push` にします。モデルのGit書き込みは禁止し、runnerが検証・commit・pushを担当します。commit/push設定では開始時にcleanなworktreeが必要です。

## ネイティブ運用

[運用手順](docs/operations.md)に従ってsource CLIと認証を準備し、`doctor` を実行します。`sandbox-check` はモデルを呼ばず、許可・拒否の両方を実測します。`serve` はこの検査に失敗すると起動しません。sandboxを無効化するfallbackはありません。

旧Lucyを残した確認は [リハーサル](docs/migration.md#リハーサル) として別profileで実施します。定期サービスの有効化・旧Lucyの停止は本番切替時だけ行ってください。Nanaは移行対象外です。

## 検証

```sh
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src assets tools tests
bin/ai-topics-codex validate
uv run python tools/check-skill-links.py
uv run python tools/check-public-tree.py
```

実モデルのテストは `tools/smoke-codex.py --live --auth-home <認証ディレクトリ>`。隔離した合成Wikiで triage → JSON handoff → Wiki生成 → index/log と raw 不変性を検証します。実行にはサブスクリプション使用枠を使います。CI は実モデルや外部通知を呼びません。

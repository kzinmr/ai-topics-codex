# 配備・日常運用

## 設定

`--profile` → `WIKI_PROFILE_ROOT` → `WIKI_SUBPROCESS_HOME` → checkoutのprofiles/lucyの順でCLI profileを選びます。runnerが子process HOMEを設定します。`bin/ai-topics-codex` はcheckoutの`.venv/bin/python`を自動利用し、`AI_TOPICS_PYTHON`で変更できます。

local.jsonの主な項目:

| 項目 | 既定 / 意味 |
|---|---|
| `codex.executable` | `codex`。必要なら実行ファイルの絶対path |
| `codex.auth_home` | profileの`.codex`。既存認証を使う場合だけ明示 |
| `codex.model`, `codex.effort` | 未指定はCodex既定。契約で利用可能な値を選ぶ |
| `codex.web_search` | `live`。`cached` / `disabled`も可能 |
| `codex.network_jobs` | tool通信を許可する調査ジョブ名の配列。空配列ですべて禁止 |
| `codex.sandbox` | 省略または`native`のみ。場所別権限profileを強制 |
| `publication` | `local`。実運用commitは`commit`、pushまで行う場合`push` |
| `environment` | 取得元、PATH、Git設定等の非機密値 |
| `delivery` | operations / digest / hot-posts のroute。既定outbox |
| `max_catchup_minutes` | 1440。長期停止は自動再生せず確認を要求 |

秘密値は`secrets.json`にJSON文字列として設定しchmod 600。shellのsourceで読み込まないため `$()` 等を実行しません。モデル用APIキーは設定しません。`account`は認証type/planと使用枠を確認し、秘密tokenやメールアドレスを表示しません。

ChatGPT authは専用profileに `login` して保存することを推奨します。共有する場合も他のplugin/configを持つ個人用CODEX_HOMEを指定せず、authだけの専用ディレクトリを使ってください。ログイン期限切れは再login後に失敗jobを明示再実行。使用上限ではリセットを待ちます。枠の追加購入・reset credit消費は自動化していません。

## Linuxの準備とsandbox検査

Python 3.12+、Node 24、Git、Codex CLI 0.157.1、配布版bubblewrapを使用します。
Python依存は `uv sync --frozen --extra collectors`、Codexは `npm install -g @openai/codex@0.157.1`。
収集CLIはGoを導入して `WIKI_PROFILE_ROOT=... tools/install-source-tools` で固定版をビルドします。
Ubuntu 24.04では `sudo tools/setup-linux-sandbox` がbubblewrapと専用AppArmorプロファイルを導入します。
既存のカスタムプロファイルは上書きせず、ホスト全体のuserns制限も解除しません。再起動を自動実行しません。
他のLinuxでは配布元のbubblewrap/AppArmor手順に従ってください。

```sh
bin/ai-topics-codex sandbox-check
bin/ai-topics-codex doctor
```

検査は合成ファイルでWiki/scratchの書き込み許可、管理ファイル・認証の読み取り拒否、
スクリプト・原文の書き込み拒否、symlink経由の読み取り拒否、ローカルTCP通信の拒否を確認します。
ChatGPT認証やモデル使用枠は `sandbox-check` には不要です。

既存profileの `codex.network_access: true` と古いsandbox指定は削除し、必要なら `network_jobs` を設定します。
`sync-assets` でprompt/skillを同期します。標準で通信を許可するのはactive-crawl、trending-topics、
x-bookmarks-ingest、x-accounts-scan、skeleton-enrich-daily、llm-pricing-monitor、dreaming-collectです。
これはshell通信の設定で、native web searchは `web_search` が別に制御します。

モデルはWikiと `~/.wiki-agent/work` を編集し、管理コード・ledger・秘密情報を変更できません。
triage/groupingではWikiも読み取り専用です。調査ジョブはraw追加のためrawに書けますが、
既存rawを変更するとrunnerが失敗として記録し、公開を止めます。自動で原文を巻き戻さないので差分を確認してください。
collectorと配送は信頼済みrunnerの処理で、Codex sandboxの外です。本番では専用OSユーザーを推奨します。

## Host service

```sh
tools/render-systemd --profile "$WIKI_PROFILE_ROOT" --python "$PWD/.venv/bin/python" > /tmp/ai-topics-codex.service
systemd-analyze --user verify /tmp/ai-topics-codex.service
mkdir -p "$HOME/.config/systemd/user"
install -m 644 /tmp/ai-topics-codex.service "$HOME/.config/systemd/user/ai-topics-codex.service"
systemctl --user daemon-reload
systemctl --user enable --now ai-topics-codex.service
```

generatorは起動自体をしません。現在のPATHをserviceに記録するため、生成するshellでNode/Codexが見えることを確認。`serve` はsandbox検査後にのみ開始します。旧Lucyを残すリハーサルではこのserviceを有効化しません。

## 日常コマンド

```sh
bin/ai-topics-codex jobs
bin/ai-topics-codex status
bin/ai-topics-codex account
bin/ai-topics-codex run wiki-health-fix --dry-run
bin/ai-topics-codex run wiki-health-fix
bin/ai-topics-codex outbox
bin/ai-topics-codex chat
```

`chat` は同じprofileとwriter lockでCodex CLIを起動するhost用入口です。定時ジョブと同じネイティブ権限制御を使い、shell通信は既定で無効です。定時ジョブと手動編集が競合しないよう、長い対話前にはserviceを停止してください。runner外での直接編集はlockが効きません。

`tick` は一度だけ定時実行処理、`serve`は15秒間隔の常駐。disabled jobも `run <name>` なら手動実行できます。`prompt <name>` で現在の指示を確認できます。

## 障害からの復帰

- `runs/<id>/result.json`, `context.txt`, `inputs.json`, `response.md`, `events.jsonl` とstatusを確認。
- 収集成功後にモデルが失敗した場合は、副作用を確認して `retry <run-id>`。元の入力でモデル段階だけ再実行します。新しい同job実行やupstream更新がある場合は古い入力を拒否します。IMAP/Xの既読・processed IDを戻す必要はありません。
- 失敗collectorは下流へ進みません。古い出力を手作業でlatestへ戻さず、原因修正後に上流から実行。
- runningが残ったら、副作用を確認し `recover <id>`。これは失敗への確定だけで再実行しません。
- 長期停止による大量catch-upを捨てるなら `reset-cursor`。未実行作業は必要分だけ `run`。
- 配信だけ失敗した場合 `outbox --deliver`。既にdeliveredの記録は再送しません。

## 配信を有効にする

明示的に配送先と認証を設定してから、該当routeを次の形式に変更します。

```json
{"kind":"command","command":["wiki-deliver"],"timeout_seconds":60}
```

bundled transportはoperations/hot-postsをDiscord、digestをTelegramへ送ります。送信は既定無効。Slack hot-posts jobのSlack操作は読み取りで、最終レポートの配送先は別設定です。別の配送先はJSON envelopeをstdinで読むcommandを設定してください。

## Backup

service停止後に `snapshot <path> --quiesced --include-content`。scheduleと運用資産はGitで管理し、authはbackupに含めません。restore先は必ずfresh profile。stateful serviceの整合はSQLite online backupだけでは保証できないため、cutover前はwriterを停止します。

## 公開の境界

`publication=local` は編集のみです。`commit` / `push` ではclean worktreeでジョブを開始し、
runnerがraw不変性と変更範囲を確認してWikiだけをstageし、content hookを通してcommitします。
モデルからGit metadataは書けません。既存の未commit変更がある場合は自動で取り込みません。
commit後のpush失敗はjob失敗です。commitは保持されるので内容を確認して管理側からpushし、
安易にモデル処理全体を再実行しないでください。初期設定のoutboxは送信しません。

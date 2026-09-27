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
| `codex.network_access` | true。host sandbox内toolのnetwork許可 |
| `codex.sandbox` | hostは`workspace-write`。Dockerはdeployment envから`external` |
| `publication` | `local`。実運用commitは`commit`、pushまで行う場合`push` |
| `environment` | 取得元、PATH、Git設定等の非機密値 |
| `delivery` | operations / digest / hot-posts のroute。既定outbox |
| `max_catchup_minutes` | 1440。長期停止は自動再生せず確認を要求 |

秘密値は`secrets.json`にJSON文字列として設定しchmod 600。shellのsourceで読み込まないため `$()` 等を実行しません。モデル用APIキーは設定しません。`account`は認証type/planと使用枠を確認し、秘密tokenやメールアドレスを表示しません。

ChatGPT authは専用profileに `login` して保存することを推奨します。共有auth_homeには他のplugin/configがあるため、同じ設定を意図して使う場合に限定してください。ログイン期限切れは再login後に失敗jobを明示再実行。使用上限ではリセットを待ちます。枠の追加購入・reset credit消費は自動化していません。

## Docker

READMEのbuild/init/loginに続き、profileの`.wiki-agent/secrets.json`とlocal.jsonを編集します。imageにはPython依存、Codex 0.157.1、blogwatcher 0.0.2、xurl 1.1.0を含みます。

```sh
docker compose -f deploy/compose.yaml run --rm lucy exec python3 /workspace/profile/.wiki-agent/scripts/import_opml.py
docker compose -f deploy/compose.yaml run --rm lucy exec xurl auth --help
docker compose -f deploy/compose.yaml run --rm lucy doctor
docker compose -f deploy/compose.yaml up -d
docker compose -f deploy/compose.yaml logs --tail=100 lucy
```

`/workspace/profile`はcontainer内部だけのpathで、promptやskillに固定しません。UID/GIDはmount所有者に合わせます。profile directoryを先に作成し、root所有の自動作成を避けます。CODEX_HOMEやX OAuth等はprofile volumeに永続化されます。host専用のauth_home絶対pathはcontainerで解決できないので、共有する場合は別途その領域を明示mountしてください。

hostで `bwrap` のユーザー名前空間が利用できない場合、hostのsandboxを自動で無効化しません。このCompose deploymentを使います。外側のDocker隔離が必須なので、privileged、Docker socket mount、host root mountを追加しないでください。

## Host service

```sh
tools/render-systemd --profile "$WIKI_PROFILE_ROOT" --python "$PWD/.venv/bin/python" > /tmp/ai-topics-codex.service
systemd-analyze --user verify /tmp/ai-topics-codex.service
mkdir -p "$HOME/.config/systemd/user"
install -m 644 /tmp/ai-topics-codex.service "$HOME/.config/systemd/user/ai-topics-codex.service"
systemctl --user daemon-reload
systemctl --user enable --now ai-topics-codex.service
```

generatorは起動自体をしません。現在のPATHをserviceに記録するため、生成するshellでNode/Codexが見えることを確認。container版とhost版は同じprofileに対して併用しません。

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

`chat` は同じprofileとwriter lockでCodex CLIを起動するhost用入口です。動作するユーザー名前空間が必要で、DockerのexternalSandboxモードでは利用しません。定時ジョブと手動編集が競合しないよう、長い対話前にはserviceを停止してください。runner外での直接編集はlockが効きません。

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

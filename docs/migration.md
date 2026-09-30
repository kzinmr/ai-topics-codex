# データ移行と切替

既存profileの上書きは禁止です。旧writerを動かしたままのsnapshotは **rehearsal** と明示し、本番切替には使いません。旧環境は読み取りだけで、新Codex profileへ変換します。

## 移行するもの

| 旧 | 新 |
|---|---|
| `.hermes/cron/data` | `.wiki-agent/checkpoints` |
| `.hermes/cron/output/<legacy-id>` | `.wiki-agent/outputs/<job-name>` |
| `.hermes/processed_*.json` | `.wiki-agent/processed_*.json` |
| `.hermes/scripts/cache` | `.wiki-agent/scripts/cache` |
| `.ai-topics-agent/runs.db`, runs, outbox | `.wiki-agent` 内の同等state |
| `.blogwatcher/blogwatcher.db` | 同じprofile相対位置（SQLite online backup） |
| Wiki / inbox / transcripts / feeds / content hooks | content repository内の同じ位置 |

snapshot version 2 / layout `codex-v1`。checksum、archive member、容量上限、path traversal、symlink、重複を検査してから復元します。Git tracked deletionと未commit内容もcontent snapshotへ反映。raw source本文は書き換えず、構造化checkpointのpath値を新profileへ移します。過去の自由文ログは歴史資料として残ります。

旧出力の最後が失敗・JSON不正なら `latest.json` を生成しません。古い成功を最新に偽装せず、ledgerが下流の実行を止めます。旧schedule claimを過去にさかのぼって再生しません。

認証情報、`.env`、Codex auth、X OAuth store、SSH/Git credential、native binaries、gateway sessions、旧agent設定、旧skillは移行しません。取得元・Git・Codexの認証は配備先で設定します。

## リハーサル

以下の変数には実際のsource/destinationを設定します。sourceは変更しません。

```sh
export OLD_PROFILE=/path/to/old/lucy
export NEW_PROFILE="$PWD/profiles/lucy-rehearsal"
mkdir -p backups
bin/ai-topics-codex --profile "$OLD_PROFILE" snapshot "$PWD/backups/lucy-rehearsal.tar.gz" --legacy --include-content
bin/ai-topics-codex --profile "$NEW_PROFILE" init --content-source "$OLD_PROFILE/ai-topics"
bin/ai-topics-codex --profile "$NEW_PROFILE" restore "$PWD/backups/lucy-rehearsal.tar.gz" --rehearsal
bin/ai-topics-codex --profile "$NEW_PROFILE" exec python3 "$NEW_PROFILE/.wiki-agent/scripts/wiki_health.py" --json
bin/ai-topics-codex --profile "$NEW_PROFILE" run blog-triage --dry-run
```

`init --content-source` はローカルのGit履歴をcloneし、originを `kzinmr/ai-topics` に設定します。続くrestoreがsnapshot時点の未commit内容と削除を反映します。raw・checkpointの実在性を確認し、preview中はpublication=local / outboxを維持してください。

## 本番cutover

1. 旧Lucyのwriterを停止し、進行中のWiki編集を終える。旧Lucyの定期実行を、その環境のサービス管理手順で停止する。Nanaや共有サービスは停止対象ではありません。HermesのCLI操作が必要な場合は元repositoryの `bin/hermes-lucy` wrapperだけを使います。
2. 新しいファイル名で `snapshot --legacy --include-content --quiesced`。quiescedは利用者による「writer停止済み」の表明で、ツールが他hostのwriterを止めるわけではありません。
3. **新規profile**をinitし、`restore <bundle>`（`--rehearsal`なし）。既存restore先へ重ねません。
4. `login`、取得元認証、source CLI、Git identity/credentialsを設定。`doctor` と `account` を確認。
5. 必要なら実行中断履歴を `status` で確認して `recover <run-id>`。失敗した段階は上流から順番に明示再実行。
6. 実データで少量を処理し、原文不変・差分・tag/index hooksを確認。Git push運用ならlocal.jsonのpublicationをpushへ設定。
7. 新schedulerを一つだけ開始。旧writerは停止状態のまま。最初の各パイプラインとoutboxを確認。

contentへのpushはこの運用設定による別の外部操作です。成果物repositoryをpushしたことだけでcontentの自動pushやメッセージ送信が有効になることはありません。

## Rollback

新schedulerを停止し、進行中のprocessが終了したことを確認。新profileをsnapshotして保持します。旧profileは変換処理で変更しないため戻せますが、新側で取得・公開した分を確認せず旧writerを再開しないでください。IMAP既読・外部送信・Git pushはprofileを戻しても巻き戻りません。新旧を同時稼働させないことが最優先です。

## アセット更新

コード更新後は `sync-assets`。installerが管理hashを比較し、local driftがあれば停止します。変更をsourceへ取り込むか、installedファイルを別途private backupへ退避してから再同期します。ローカル改変を無条件に消すforce optionはありません。

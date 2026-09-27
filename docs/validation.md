# 検証記録 — 2026-09-27

## 自動検証

`python -m unittest discover -s tests -v`: **50 tests passed**（25.227秒、最終機能変更後）。

- UTC cron、schedule重複claim、writer lock、dependency鮮度・失敗、skip伝播。
- collector失敗、JSON error、no_agent、wakeAgent gate、outboxと本処理の成否分離。
- ChatGPT以外の認証拒否、API環境変数の非継承、使用枠上限での停止。
- App Server完了・拒否・モデル失敗・EOF・対話承認要求・timeout。
- strict JSONの必須項目、重複ID、実在するtake原文、group ID、checkpoint一致、candidate処理漏れ。
- モデル失敗後のretryでcollectorを再実行しないこと、古いrunのreplay拒否。
- asset drift保護、symlink escape拒否、パスに空白があるprofile。
- legacy ID/path変換、SQLite WAL backup、秘密情報の除外、archive traversal拒否、Git tracked deletion保持、hook実行bit保持。
- RSS取得失敗の未読保持、sitemap未取得URLの未処理保持、raw不変性、newsletter空checkpoint。

全Python資産をcompileall。core/test/toolの未定義・未使用参照、全assetの未定義参照をruffで確認。23スキルをCodex skill validatorで検証。skill link欠落0、公開ツリーのcredential/path検査0件。sourceの秘密値との照合も値を表示せず実施しました。

## 現行Lucyとの一致

live jobs.jsonとmanifestをID mapで照合: **30件・有効27件・時刻/停止状態のdrift 0件**。

稼働中sourceからrehearsal snapshotを作成し、別profileへ新形式で復元しました。これは整合停止済みcutover snapshotではありません。

| 検証 | 結果 |
|---|---|
| legacy → native restore | 20,389ファイル |
| `.hermes` runtime directory | destinationに作成されない |
| content pre-commit hook | 実行bit維持 |
| Wiki health JSON | 正常生成、約2.1秒 |
| L2 | entities 935 / concepts 2,101 / comparisons 35 |
| raw/articles | 9,945 |
| blog checkpoint | 19候補、19件のraw pathが存在 |
| newsletter checkpoint | 100候補、100件のraw pathが存在 |
| contentの既存orphan | 2件。移植とは別の既存問題として保持 |

旧最新triage出力は失敗ログだったため、成功した `latest.json` に変換されません。これを移行失敗として隠さず、旧失敗の引き継ぎとして扱っています。

## 実Codex検証

Codex CLI **0.157.1** の `app-server generate-json-schema` とrequest fieldsを照合。
実App Serverで `account/read` と `account/rateLimits/read`、ChatGPTログイン状態を確認。

このhostのworkspace-write shellは `bwrap: setting up uid map: Permission denied` により失敗しました。モデル応答とJSON出力までは成功。host sandboxを無効化するfallbackは追加していません。

代わりに、非root / read-only root / cap_drop ALL / no-new-privileges / tmpfs profileのDockerで実モデルを実行し、ファイル作成・読み戻し・strict JSON応答に成功しました。hostのauth.jsonはread-only mountのみで、imageやGitへコピーしていません。

さらに `tools/smoke-codex.py --live` で合成記事を使った実パイプラインを実行:

1. 正常なblog collection checkpointを作成。
2. 実Codexによるblog-triage → strict JSON検証 → `latest.json`。
3. 実際のblog_triage_checkpoint.pyを経由してblog-wiki-ingest。
4. Wikiページ、source URL、実験の数値と限定条件、index/log更新を検査。
5. 原文のSHA-256不変を検査。

合成データの機能試験です。本番記事の長期品質や全収集元の取得成功率を証明するものではありません。

## 配備

Codex専用Docker imageのbuild成功。Compose config、生成systemd user unitのverify成功。固定モデル名やAPI keyなしで実モデル試験を通しました。

CIは同じofflineテスト・compile・manifest/skill/public-tree検査・Compose構文検査を実施します。モデル認証と通知先をCIに渡しません。

## 実行していない操作

本番IMAP/X等の取得、Discord/Telegram送信、生成記事のcontent push、本番writerの停止・新schedulerの常駐開始、Nanaの変更は未実施です。これらの設定・切替手順はoperations/migrationにあります。private snapshot、実行ログ、認証情報は成果物に含めません。

# Docker撤去とネイティブ運用の検証

2026-09-27。旧Lucy/Nanaは稼働・構成とも保持し、新しい定期serviceは有効化していない。
検証には独立した合成profileと、旧Lucyから複製したリハーサルprofileを使用した。

## 変更

- Dockerfile、Compose、container marker、externalSandbox分岐とCIのDocker検査を撤去。
- Codex 0.157.1の場所別permission profileへ統一。管理コードは読み取り専用、認証はアクセス拒否、Wikiと専用scratchだけ書き込み可能。triage/groupingはWikiも読み取り専用。
- shell通信を必要な調査ジョブだけに限定。モデルには環境変数の許可リストだけを渡す。
- 管理側runnerが原文不変性・Wiki内symlink・公開範囲を確認し、hook付きcommit/pushを実行。モデルにはGit書き込みを許可しない。
- `sandbox-check` とdoctorによる実測検査を追加。常駐serviceは検査に失敗すると起動しない。
- Ubuntu 24.04向けのhost設定スクリプトと、事前検査・資源制限付きsystemd unit生成を追加。

## ホスト

Ubuntu 24.04.4 / Linux 6.8.0-134 / Codex CLI 0.157.1。
利用者が `sudo tools/setup-linux-sandbox` を実行し、配布版bubblewrapと専用AppArmorプロファイルを導入した。
`kernel.apparmor_restrict_unprivileged_userns=1` のまま、標準sandboxの起動に成功した。
以前のuid map/loopbackエラーはこの構成で解消した。
パッケージ導入時にカーネル更新待ちの通知が出たが、再起動やDocker serviceの再起動は実施していない。

## 実測

| 検証 | 結果 |
|---|---|
| オフライン回帰 | 59テスト成功。compileall、未定義名・未使用import検査、ジョブvalidate、skill参照、公開tree検査も成功 |
| App Serverの非モデルsandbox probe | 11項目合格。許可された書き込み、管理領域・authの読み取り拒否、script/raw書き込み拒否、symlink経由の読み取り拒否、ローカルTCP拒否と原文保持 |
| systemd一時service | NoNewPrivileges=yes / TasksMax=256 / MemoryMax=4Gで同じprobeが成功。常駐schedulerは起動していない |
| systemd unit構文 | `systemd-analyze --user verify` 成功 |
| ChatGPT実モデル・合成Wiki | blog-triage → strict JSON → blog-wiki-ingest → ページ/index/log更新が成功。原文SHA256不変 |
| 移行snapshot | 20,409ファイルを別profileへ復元。稼働中sourceなのでrehearsalと明記 |
| 移行Wikiのローカルhealth | L2 3,071ページ、raw articles 9,963件。命名違反0、既存孤立ページ2件 |
| checkpoint reader | blog候補18件/18path、newsletter候補100件/100pathが新profile内の実ファイルを参照 |
| 移行先doctor | `--job blog-triage` で認証、sandbox、依存、hooks、管理資産すべて合格 |
| 補助CLI | blogwatcher 0.0.2 / xurl 1.1.0をホスト向けにビルド成功。収集は実行していない |
| 旧サービス | Lucy/Nanaとも継続稼働。旧Lucyは30ジョブ中27有効を維持 |

実モデル試験は `tools/smoke-codex.py --live --auth-home <専用認証ディレクトリ>` で再現できる。
認証情報や実行ログは公開repositoryに含めない。公式文書と導入済みCLIのスキーマを確認し、
古いsandboxPolicyで場所別権限を上書きしないことを実装上の契約とした。

## 検証範囲

実モデルに渡したのは合成データだけである。移行した実原文の追加モデル読取試験は、具体的なpayloadの
外部送信に関する自動承認審査で拒否され、実行していない。実データの整合性確認はローカルで完了した。

本番の取得元認証はコピーしておらず、IMAP/X/Slackの接続、既読化、外部への通知、content pushを実行していない。
通常の全ジョブdoctorや、30ジョブの実時間スケジュールを通した本番運転の成功を意味しない。
旧Lucyと新schedulerの同時運転を避け、今後の切替時に取得元認証と配信先を設定する。

collector/scheduler/配送はCodex sandbox外の信頼済み処理である。専用OSユーザーでの配備を推奨するが、
今回の検証は既存ユーザーの別profileで行った。調査ジョブによる既存raw変更は検出・公開阻止するが、
自動復元しない。`publication=commit|push` の開始時にはclean worktreeが必要。

[設計上の評価](docker-free-assessment.md) / [運用手順](operations.md) / [移行手順](migration.md)

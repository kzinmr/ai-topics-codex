# Lucy の Codex ネイティブ移植レポート

> 初回移植時の履歴。現在の状態は [ネイティブ移行検証](native-validation.md)。


調査・実装日: 2026-09-27。移植元 `ai-topics-agent` は commit `b87a0a20246e08c97ddbf5eacfcffcdbfeaf4bc1`。Lucy のlive設定・checkpoint・content treeも読み取り確認しました。

## 課題と変更

旧成果物はschedulerを分離していましたが、実行方式の既定はHermes、`.hermes`をディスク互換ABIとして保持し、旧skillのツール名・過去セッション指示を大量に注入していました。Codexへのtransport切替だけでは、運用上の依存とprompt上の依存が残ります。

このrepositoryでは実行方式をCodexに固定し、状態形式、認証、スキル、prompt、deployment、migrationを同時に変更しました。既存 `ai-topics-agent` と本番Lucyの稼働設定は変更していません。

| 観点 | 以前 | 移植後 |
|---|---|---|
| モデル実行 | Hermes/pi/Codex adapter | Codex App Serverのみ |
| モデル認証 | providerごとの設定 | ChatGPT loginを検査、API fallbackなし |
| state | `.hermes/cron/*` + runner state | `.wiki-agent` に統合 |
| job ID | 旧schedulerのランダムID | 読めるjob名 |
| skill | 旧tool名・大量のセッション記録 | Codex形式23個、領域ルールと必要なhelpers |
| job prompt | 通知先・ツール・歴史的指示が混在 | 30ジョブを各タスクに再構成 |
| stage連携 | Markdownの `## Response` を抽出 | schema検証済みJSONのatomic handoff |
| Wiki規約 | tracked AGENTSがHermes前提 | local AGENTS.overrideでCodex契約を適用 |
| 使用量 | COST_REPORTのテキスト推定も存在 | Codexの実測usageのみ |
| 配備 | 複数ハーネスimage | Codex専用image + host service |

既存のドメインロジックは、RSS取得失敗の未読保持、IMAP Message-ID dedup、X cursor/cache、sitemap処理済URL、raw不変性、tag/index検査、archiveのdecision保持を再利用しました。旧skillの長大なセッション例はactive promptにコピーせず、核心となる判断規則にまとめました。元資料の追跡情報は [source-inventory.json](source-inventory.json) にあります。

## OpenAI 実行方式の選択

| 選択肢 | このプロジェクトへの判断 |
|---|---|
| Codex App Server | **採用**。ローカルWiki・shell・認証状態・usage・構造化応答を一つの公式実行基盤で制御できる |
| Codex SDK（Python / TypeScript） | 有効な代案。既存Pythonのscheduler/collectorを維持し、今回必要なstdio契約を小さなclientで直接実装したため追加しない |
| Agents SDK + Responses API | 独自tool loopを作る必要が増す。今回の「既存サブスクリプションを基盤にする」経路には採用しない |
| Agents API | OpenAIがCodex harnessを管理する選択肢は存在する。ただしAPI keyの権限・API環境設定が前提なので今回の主経路には採用しない |

Codex SDKはローカルthreadを操作でき、Python SDKもApp Serverを利用します。[公式SDK資料](https://learn.chatgpt.com/docs/codex-sdk)

Agents API / Agents SDK / Responses APIは、それぞれmanaged harness / application agent loop / model integrationという所有範囲の違いがあります。[公式runtime比較](https://developers.openai.com/api/docs/guides/agents)

Agents APIを「存在しない」とは扱っていません。現行quickstartのAPI-key要件と、このプロジェクトのサブスクリプション要件を比較した設計判断です。[Agents API概要](https://developers.openai.com/api/docs/guides/agents-api/overview)

ChatGPT loginの有効期限・モデル利用可否・使用枠はCodexと契約に従います。「定額だから無制限」や「ChatGPT OAuth tokenで任意のAPIを利用できる」とは仮定していません。

## 現行データと運用の理解

Lucyはraw sourceからcurated Wikiへ知識を統合し、schema / index / logで再利用可能性を維持するシステムです。単なる記事の要約保存やRSS通知ではありません。

主要パイプラインはblog、newsletter、dreamingの3段階連鎖。X bookmark/account、sitemap、active crawlが収集範囲を補完し、graph、health、tag、hierarchy、translation、pricing、digestが継続的な維持管理を行います。元のUTC時刻とdisabled状態を [jobs.md](jobs.md) に整理しました。

実データの復元でL2 3,071ページ（entities 935、concepts 2,101、comparisons 35）、raw記事9,945件を観測しました。health出力のorphan 2件は移植先にも残した実コンテンツの問題で、移行作業として勝手に削除していません。

旧最新triageのログには失敗がありました。移植はこれを成功済みの入力へ変換しません。collectorの保存済rawとdedup状態は引き継ぎ、失敗した段階は新実行基盤で明示的に再実行します。

## 実装中に判明した問題と対処

- App Server終了後のstdin closeでBrokenPipeが元のエラーを隠す問題を修正。
- 初回のhost sandbox起動時にuid mapエラーを確認。後続のホスト設定と検証は [ネイティブ移行検証](native-validation.md) に記録。
- restoreでGit hookの実行bitが失われる問題を修正し、doctorと回帰テストを追加。
- dreamingのrun IDが `_checkpoint.run_id` にある場合も照合。
- 上流skip時に古いtriageを再利用しないようskipを伝播。
- 収集後のモデル失敗に対する入力replayを実装し、既読・processed ID更新済み項目の取りこぼしを防止。
- skill helperのmetadata修復関数欠落を静的検査で検出し補完。

## 引き渡し範囲

コード、運用資産、変換ツール、コンテナ、host service generator、CI、移行・復旧手順、検証記録をこのrepositoryに収めました。secret、auth、snapshot、実行ログ、Wiki本文は公開成果物に含めません。

稼働中Lucyの停止と本番scheduler切替、実サービスのメール取得・X取得・通知送信、content repositoryへの生成記事pushは実施していません。これは移植成果物の作成・実証と、稼働系の切替を分けたものです。稼働系切替は [migration.md](migration.md) のquiesced手順で行います。Nanaは対象外です。

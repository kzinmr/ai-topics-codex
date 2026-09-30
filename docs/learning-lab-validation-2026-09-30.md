# 現行ドラフト検証とCodex SDK学習実験

検証日: 2026-09-30。実行環境: macOS arm64、Python 3.12.5。
対象: ai-topics-codex `3bf7d0d`、ai-topics-agent `b87a0a2`に本検証の小修正を適用。
既存の未commit設計文書は維持。Lucy/Nana、本番collector、通知、remote Gitには変更なし。

## 現行ドラフトの検証結果

| 検査 | 結果 | 範囲 |
|---|---|---|
| Codex版 unittest | 62件成功 | 元の60件＋終了処理の回帰2件。外部サービスはfixture |
| ハーネス非依存版 unittest | 30件成功 | Hermes/pi/Codexのprotocol fixtureを含む。実Hermes/piは未起動 |
| compileall / validate / skill links / public tree | 両repositoryで成功 | agent版に既存のescape SyntaxWarningあり。skill参照欠落・credential-like検出は0 |
| Codex native sandbox probe | 11項目成功 | checkoutの`.local`配下で実CLIを使用。モデル呼出しなし |
| 現行runnerの実モデルsmoke | 成功 | 合成Wikiのtriage→JSON handoff→Wiki生成、index/log、raw SHA256保持 |

Codex CLIはアプリ同梱の`0.158.0-alpha.2.1`。Linuxでの過去検証版`0.157.1`とは異なる。
この結果は、Mac上で確認した経路の互換性を示すもので、全30ジョブの本番稼働を保証しない。
メール/X接続、通知、定時サービス、commit/pushの実運用試験は実施していない。

依存は`uv sync --frozen --extra collectors`で固定版を導入。
オフライン回帰は`TMPDIR=/private/tmp`で実行した。Macの`/var`と`/private/var`の表記差によるfixture比較を避けるため。
これは実モデル用profileの置き場所とは異なる。

### 検証中に修正したもの

**プロセス終了処理。** EOFで既に終了した子processのgroupにsignalを送る際、macOSでPermissionErrorが生じ、
本来のEOFを隠していた。両版の`stop()`で先に`poll()`して終了済みleaderを回収する。
groupへのsignalは引き続き行うため、leader終了後に残る子孫processを見落とす早期returnにはしない。
PermissionErrorを一律に握りつぶさず、回帰テストでも確認した。

**実モデルsmokeのprofile配置。** OSの一時ディレクトリでは、control read/write・symlink escape等が拒否されず、
11項目のうち4項目が失敗した。同一CLI・同一policyでもcheckout内の`.local`配置では全項目成功した。
OS一時領域への暗黙のアクセス許可が影響している可能性があるが、CLI内部原因の特定までは行っていない。
`smoke-codex.py`は`.local/smoke-profiles`を使い、モデル実行前に実測probeを必須に変更した。
拒否境界を緩める変更やsandbox無効化はしていない。

## 次の作業として準備したもの

[SDK実験](../experiments/codex-sdk/README.md)を本番runnerと分けて追加した。

- 公式Python `openai-codex==0.159.2`を別venvへ導入。
- App Server版と同じアプリ同梱CLIを明示して使用。SDK同梱CLIへの暗黙の切替を避けた。
- 公開記事5件＋既存Wikiページ2件をhashで固定。全文とその要約の組を含む。
- 固定入力から最大2ページの更新を行い、判定JSON、実変更、raw保持をコードで照合。
- 認証は既存ChatGPTログインを参照し、secretをコピーしない。API-key fallbackなし。
- 推論とは別に、認証方式、使用枠、sandbox境界、成果物の検証をアプリ側に残す。

実データ送信は最初に自動承認審査で拒否された。
その後、ユーザーが`corpus.json`の7ファイルをOpenAIへ送ることを明示承認した。
承認前に実データを送信せず、自作の合成入力だけでSDKの実行確認を進めた。

### SDKを実際に触って分かった差分

1. SDKはJSON-RPCやthread/turn、型付き結果を扱う。Wikiの処理済み台帳・raw保護・公開は自動では引き受けない。
2. `CodexConfig.env`は継承環境の置換ではなくoverlay。runnerのsecret allowlistと同じ意味にはならない。
   本実験では専用processの環境をallowlist化してからSDKを起動する。
3. `TurnResult.status`は列挙型。最初の合成実行ではモデルturnがcompletedでも、実験コードが文字列比較とJSON保存に失敗した。
   `.value`とJSON向けserializationへ修正。失敗runは成功と書き換えず保存した。
4. native permissionはSDKのsandbox presetで上書きせず継承できる構成を使った。
5. 使用枠の事前確認は既存App Server呼出しを再利用した。独自RPCを完全撤去した試作ではない。

## SDK実データ実行

**成功。** run ID: `20260930T141224-597000`。

| 項目 | 結果 |
|---|---|
| SDK / CLI | `0.159.2` / `0.158.0-alpha.2.1` |
| 認証 | ChatGPT。API-key fallbackなし |
| 実行前sandbox | 11項目成功 |
| 入力 | 許可済み記事5件・Wikiページ2件の固定コピー |
| 判定 | take 3、reference 1、skip 1。5件のIDが完全一致 |
| 編集 | 既存2ページ、index、log。報告pathと実diffが完全一致 |
| 原文 | 全5件のSHA256不変。SCHEMAも変更なし |
| 所要時間 | SDK実行区間116.64秒（準備・probe・事前認証確認を除く） |
| SDK usage | input 240,442、うちcached input 196,480、output 3,224、total 243,666 |
| 行動 | SDK itemsにshell実行7件を記録。read→追加読解→編集→自己検証 |
| Git / 外部副作用 | 実験準備のbaseline commit 1件のまま。remoteなし、通知・pushなし |

usageは複数モデル呼出しの累積であり、教材の単独token数ではない。サブスクリプション費用をAPIドルに換算しない。
モデル名は明示固定せずCLI既定を使用したため、モデル差を切り分ける性能比較には使用しない。

実際の差分も確認した:

- 同一記事の要約をskipし、全文と二重に裏付けとして数えなかった。
- Cursor記事の2023年の公開日と2026年の取得日を区別した。
- 既存の並列Agentの利点を消さず、後の資料にある協調の難しさを追記した。
- OpenAI記事のPR数増加を、skillの因果効果が証明されたものとして扱わなかった。
- 既存本文を残して根拠付きの節を追加し、index/logを同期した。

この確認は保存された資料と差分の範囲であり、引用先の外部研究や現在の製品仕様の再検証ではない。
成果物は`.local/codex-sdk-lab/runs/20260930T141224-597000/`の
`answer.json`、`changes.diff`、`items.jsonl`、`result.json`、`sandbox.json`に保存した。

## 学習上の位置づけ

現行runnerの合成smokeとSDKの実データ実験は、入力もpromptも違うため性能比較ではない。
今回の目的は、SDK経由の実行、境界継承、成果物検証を体験し、誰がどの責務を持つか確認すること。
次にResponses API版を作る際は、この固定入力・期待する成果物・評価を再利用する。
APIの利用条件・予算は、その実験の開始前に決める。

参照: [Codex SDK公式資料](https://learn.chatgpt.com/docs/codex-sdk)

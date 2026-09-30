# Codex SDKでWiki更新を観察する

本番runnerとは独立した学習用の実験。公式Python SDK `0.159.2`を使用する。
現行App Server版で合成Wikiの試験を通した後、同じnative permission設定をSDKへ渡す。
API-key fallback、scheduler、collector、通知、pushは使用しない。

## 入力と出力

- `corpus.json`: 既存ai-topicsの公開記事5件・関連Wikiページ2件のpathとSHA256。
- `prepare`: hash照合後、`.local/codex-sdk-lab/corpus/`へ固定コピーする。元Wikiは変更しない。
- `run --synthetic`: 自作の合成記事5件・ページ2件だけを使用する。content repositoryを読まない。
- `run`: 固定した実データを使用する。内容を認証先OpenAIへ送信するため、入力範囲の許可を得て実行する。
- 結果は`.local/codex-sdk-lab/runs/<run-id>/`。prompt、answer、SDK items、usage、diff、sandbox検査結果を保存する。

公開記事のコピーはhistorical snapshot。全文と要約を区別し、同じ記事の別表現を独立した証拠として数えない。
Wikiは部分snapshotなので、除外したページへのリンクが解決しないことを全面的に修復してはいけない。
この小さな教材には人手の正解ラベルがなく、性能benchmarkではない。
合成教材には重複、異なる実験条件での相反する測定、ログイン画面、無関係な記事を含める。

## 再現

repositoryルートで、本番とは別のSDK環境を用意する。

```sh
uv venv .local/sdk-venv
uv pip install --python .local/sdk-venv/bin/python -r experiments/codex-sdk/requirements.txt
.venv/bin/python experiments/codex-sdk/run.py prepare --content ../ai-topics
.local/sdk-venv/bin/python experiments/codex-sdk/run.py run --live --synthetic --auth-home /path/to/existing/codex-home
```

実データの送信を許可した場合のみ、最後のコマンドから`--synthetic`を外す。
認証情報はコピーしない。`--codex-bin`で検証済みCLIを明示できる。既定はPATHのCodex。
SDK同梱CLIへ暗黙に変更せず、App Server版と同じCLIで比較する。
`--deadline`の既定は600秒で、超過時はturnをinterruptする。
この値はturnの予算であり、ネットワーク断時を含むプロセス全体の強制終了保証ではない。

## SDKが担うものと実験コードが担うもの

| SDKに任せる | 実験コードに残す |
|---|---|
| App Server起動、JSON-RPC、thread/turn、結果収集、interrupt | 入力固定、認証方式と枠の検査、権限設定、原文hash、差分の実測、成果物保存 |
| 型付きの最終結果・tool items | 候補IDの完全一致、許可path、編集ページ数、reported changesとの一致 |

`sandbox=`は省略し、native permission profileを継承する。起動前に非モデルprobeが全項目通らなければ止める。
SDKの`env`は環境変数の置換ではなく追加・上書きであるため、この専用実験processで環境をallowlist化してからSDKを起動する。
認証確認にはSDKを使うが、使用枠の事前確認は既存runnerの小さなApp Server呼出しを再利用している。
したがって、この試作は独自RPCを完全に撤去した実装ではない。

判定JSONと実際の変更ファイルが一致しても、主張の正しさが保証されたわけではない。
`changes.diff`と引用先を人が読むことを学習手順に含める。
SDK実験は候補workspaceの編集までで、productionの公開成功と同一視しない。

参照: [公式Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)

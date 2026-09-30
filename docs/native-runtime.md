# ネイティブ実行環境

Python runner と Codex App Server をホスト上で直接実行します。
モデルのツールには Codex の `wiki-native` permission profile を適用します。
ランタイムの言語による権限制御ではなく、Codex が OS の隔離機構を使います。

## 配備

README に従って固定依存と Codex CLI を導入し、専用 profile を初期化します。
Ubuntu 24.04 では `sudo tools/setup-linux-sandbox` で配布版 bubblewrap と専用 AppArmor
profile を準備します。グローバルな user namespace 制限は無効化しません。
認証やモデル呼出しの前に `bin/ai-topics-codex sandbox-check` を実行できます。

`sandbox-check` は実 App Server の command/exec で許可・拒否を検査します。
service は検査に失敗すると起動せず、隔離なし実行への fallback はありません。
OS 起動には `tools/render-systemd` で生成した unit を使用します。
詳細は [運用手順](operations.md) と [実測記録](native-validation.md) を参照してください。

## 権限境界

| 対象 | 権限 |
|---|---|
| Wiki / scratch | 編集ジョブで書込み可能。triage/grouping は Wiki も読取り専用 |
| scripts / checkpoints / outputs | 読取り専用 |
| authentication / secrets / local 設定 | モデルのツールからアクセス拒否 |
| raw | 通常は読取り専用。調査ジョブの既存原文変更は runner が検出し公開を阻止 |
| 通信 | 明示した調査ジョブのみ許可 |
| Git 公開 / 収集 / 通知 | 信頼済みホスト runner の責務 |

collector・scheduler・配送処理はモデル用 sandbox の外で動きます。
本番配備には専用 OS ユーザーを推奨します。原文変更の検出は自動復元を意味しません。
CI も同じホスト構成で回帰テストと sandbox 検査を行い、実アカウント認証を必要としません。

旧Lucy/Nanaの停止や新schedulerの有効化は、コード配備と別の切替作業です。
同じコンテンツに複数の writer を同時接続しないよう [移行手順](migration.md) に従います。

# Docker依存撤去の評価

2026-09-27。対象は ai-topics-codex、確認版は Codex CLI 0.157.1。
この文書は実装前の設計レビューとして保存する。後続実装・検証の状態は [ネイティブ移行検証](native-validation.md) を参照。本番切替は利用者の指定により実施しない。

## 判断

Docker依存を撤去し、ホスト上のCodex App Server + 標準sandboxを正式な運用経路とする方針を推奨する。
ChatGPTサブスクリプション認証、現在のジョブ管理、Wiki処理のためにDockerは必要ない。
この目的で別のモデルAPIへ移る必要もない。

ただしCodexのsandboxが保護する範囲と、現在のComposeがまとめて保護する範囲は異なる。
Dockerファイルを削除するだけでは安全性の同等性を確認できない。
初回移植でホストのsandbox起動失敗からDocker経路を案内した判断は早すぎた。
ホストの前提条件を調べ、標準sandboxを正常に起動させることを優先する。

## このホストで確認したこと

| 項目 | 実測 |
|---|---|
| OS | Ubuntu 24.04.4 LTS / Linux 6.8 |
| CLI | codex-cli 0.157.1 |
| 通常ユーザー名前空間 | `kernel.unprivileged_userns_clone=1` |
| AppArmorの制限 | `kernel.apparmor_restrict_unprivileged_userns=1` |
| 名前空間数の上限 | `user.max_user_namespaces=115067`、ゼロではない |
| 外部bubblewrap | PATH上に `bwrap` なし、`/usr/bin/bwrap` なし |
| 専用AppArmorプロファイル | `/etc/apparmor.d/bwrap-userns-restrict` および追加プロファイルの配布パスに存在しない |
| 診断プロセス | AppArmor `unconfined`、Seccomp 0、NoNewPrivs 0 |
| 仮想化の検出 | `systemd-detect-virt` は `none` |

モデルや認証情報を使わず、一時HOME/CODEX_HOMEと作業ディレクトリで次を実行した。

```sh
codex -c 'sandbox_mode="workspace-write"' \
  -c 'sandbox_workspace_write.network_access=false' \
  sandbox -- /usr/bin/true

codex -c 'sandbox_mode="workspace-write"' \
  -c 'sandbox_workspace_write.network_access=true' \
  sandbox -- /usr/bin/true
```

両方ともexit 1。network=falseでは `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`、
network=trueでは `bwrap: setting up uid map: Permission denied`。
一時CODEX_HOMEについて補助バイナリを配置できない旨の警告も出たため、
正式な再検証には専用profileを用いる。先行の専用profileによるApp Server試験でもuid mapエラーを確認している。

AppArmorの制限と配布版bubblewrap未導入が有力な原因候補である。
監査ログによる原因確定やパッケージ導入後の成功確認は行っていない。
したがって「このホストではDockerが必須」「AppArmorを直せば必ず成功する」のどちらも結論にはしない。

[OpenAIのsandbox手順](https://learn.chatgpt.com/docs/sandboxing)は、Linuxで配布版bubblewrapを導入し、
Ubuntu 24.04では必要に応じて専用AppArmorプロファイルをロードする方法を説明している。
標準sandboxは起動されたコマンドにも適用される。
このプロジェクトでは、ホスト全体のAppArmor制限解除を既定の解決策にしない。

## 現行実装の境界と不足

| 対象 | 現在の動作 | Dockerなしに向けた対応 |
|---|---|---|
| モデルのshell・ファイル操作 | `workspaceWrite`、追加writable rootはprofile全体 | Wikiとジョブ専用作業領域に書き込みを限定する |
| collector / checkpoint reader | runnerがCodex外で直接subprocess実行 | 信頼済みコードをモデルの書き込み領域から分離する |
| scheduler / ledger / 設定 | profileに同居 | モデルから変更できない管理領域に分離する |
| 収集・配信の秘密情報 | 環境変数はモデルから除去するが、profile内の秘密ファイルは読みうる | ツールの読み取り境界を別途設ける。書き込み制限だけでは秘匿できない |
| ネットワーク | モデルのtool networkは既定true | Wiki編集・triageは原則不要。取得処理や調査ジョブと分離して必要範囲だけ許可する |
| 公開・通知 | promptのpublication指定とoutbox | 外部への副作用は管理側が実行。prompt指示だけを禁止の保証にしない |
| 常駐処理 | systemd user unitは再起動・umask・プロセス終了を設定 | 専用サービスユーザー、ファイル権限、資源上限を運用設計に含める |
| doctor | 設定と認証を検査、sandbox実行を検査しない | 非モデルの起動・許可・拒否テストを追加し、異常時はスケジューラを起動しない |
| 配備・CI | Dockerfile、Compose、externalSandbox分岐とCompose検査 | ネイティブでの受け入れ後、サポート経路とCIから撤去する |

特に `~/.wiki-agent/scripts` は現在モデルに追加書き込み許可するprofileの配下にあり、
runnerは次回それをsandbox外で実行する。将来のsandbox外実行に影響できるため、優先して分離すべき境界である。
Codex自身が保護する一部の管理ディレクトリがあるとしても、任意の独自scriptsディレクトリまで保護されるとは扱わない。

また、現在のDockerでもprofile内の秘密情報や管理ファイルの相互アクセス問題は残る。
Dockerの有無だけで解消する問題ではない。

## 推奨する構成

1. 専用OSユーザーでPython runnerとCodex App Serverを動かす。個人HOME、他profile、管理用Git認証を暗黙に共有しない。
2. 運用コード・設定・スキル・収集プログラムはモデルから書けない場所に置く。Wikiの入口 `~/wiki` は維持する。
3. collectorが原文とcheckpointを作り、モデルには必要な入力のみ渡す。原文は読み取り専用、編集結果はWikiまたはジョブ専用領域に限定する。
4. ledger更新、検証済みJSONの確定、通知、Git pushは管理側が担う。モデルからその管理コードや認証情報へ到達できない境界を設ける。
5. Codex標準sandboxを必須にし、無人処理は承認なしで境界内だけ実行する。起動できなければジョブを失敗させる。
6. OSパッケージ・Python lock・Codex版・source CLI版をネイティブのインストール手順で固定する。Docker imageが担っていた環境再現性をここで補う。

専用OSユーザーだけでは、そのユーザーが読めるサービス内の秘密情報をモデルから隠せない。
Codexの読み取り制限やOSのファイル隔離、必要に応じたcollector/配送の別ユーザー化を組み合わせ、実測する。
読み取り制限のない `workspace-write` と別ディレクトリへの移動だけで秘密が保護されたとは扱わない。

systemdの隔離設定も、Codexが必要とする名前空間の作成を壊さないよう検証する。
user unitにセキュリティ設定を列挙するだけでsystem serviceと同等の隔離が得られるとは主張しない。

## 撤去完了の受け入れ条件

- 配布版bubblewrapと必要なAppArmorプロファイルを準備したホストで標準sandboxが起動する。
- 許可したWiki領域への書き込みが成功し、領域外、運用スクリプト、設定、ledgerへの書き込みが拒否される。
- 認証情報、他profile、個人HOMEの読み取りを拒否できる。ネットワーク不要ジョブの外部通信も拒否される。
- 検査には秘密を含まない合成ファイルとローカルのテスト用通信先を使う。
- 既存の合成Wikiによる実モデル triage → JSON → Wiki/index/log とraw不変性テストがDockerなしで成功する。
- collector、排他、再試行、復旧、outbox、移行の既存テストが通る。
- Dockerfile、Compose、externalSandbox設定・環境変数、container marker検査、CIのDockerコマンドを撤去し、運用手順を統一する。
- 過去のDockerによる検証記録は履歴として明記して残す。本番Lucy/Nanaの切替とは分ける。

今回の調査ではOSパッケージやAppArmorポリシー、本番profileを変更していない。
ホスト単体での実モデル処理成功およびDocker撤去は未完了である。

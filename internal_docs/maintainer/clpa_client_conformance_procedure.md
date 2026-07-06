# plc-comm-slmp-python × CLPA SLMP クライアント適合試験 手順書

作成: 2026-07-07。操作ガイド BAP-C3011-001 Ver.1.3 の 3 章(クライアント機器テスト)に基づく。

## 構成

- **試験ツール(サーバー役)**: `D:\MockBuild\docment\slmp_conformance-test-tool_v1.3_j\SLMP_ClientTest_JPN.exe`(GUI・人間操作)
- **被試験機器(クライアント)**: `D:\MockBuild\plc-comm-slmp-python`(SlmpClient)
- **ドライバ**: `scripts/clpa_client_conformance_driver.py`(試験パターンの要求コマンドを発行)
- ツールの待受ポートは固定: **TCP 61442 / UDP 61443**
- 監視タイマはガイドの指示により **0000h 固定**(ドライバ既定)

## 被試験機器の申告範囲(Step2 実装仕様の入力)

plc-comm-slmp-python が対応するのは **バイナリ交信のみ(ASCII 非対応)**、フレームは 3E/4E。
申告するコマンド(= ドライバの実行項目):

| コマンド | 内容 | ドライバ項目 id |
|---|---|---|
| 0401 | 一括読出し(ワード/ビット) | 1, 2 |
| 1401 | 一括書込み(ワード/ビット) | 3, 4 |
| 0403 / 1402 | ランダム読出し / 書込み(ワード/ビット) | 5, 6, 7 |
| 0801 / 0802 | モニタ登録 / モニタ | 8, 9 |
| 0406 / 1406 | 複数ブロック一括読出し / 書込み | 10, 11 |
| 0613 / 1613 | メモリ読出し / 書込み | 12, 13 |
| 0601 / 1601 | 拡張ユニット読出し / 書込み | 14, 15 |
| 1001/1003/1002/1005/1006 | リモート RUN/PAUSE/STOP/ラッチクリア/リセット | 16–20 |
| 0101 | プロセッサタイプ読出し | 21 |
| 0619 | 折返しテスト | 22 |
| 1617 | エラーコード初期化 | 23 |
| 1631 / 1630 | リモートパスワード ロック / アンロック | 24, 25 |

ファイル系・ノード系(ノードサーチ等)・オンデマンド受信は未対応のため申告しない。

## 試験手順

1. **ツール起動**(人間): `SLMP_ClientTest_JPN.exe` → Step1 依頼者情報 → Step2 実装仕様(上表を申告、交信データコード=バイナリ)
2. **Step3 テスト実施** → 通信設定でソケット選択(TCP 61442 / UDP 61443)→ 「テスト開始」で要求待ち状態にする
3. **ドライバ起動**(同一 PC なら host は 127.0.0.1):
   ```
   cd <リポジトリルート>
   python scripts/clpa_client_conformance_driver.py                              # TCP・4E (melsec:iq-r)
   python scripts/clpa_client_conformance_driver.py --transport udp              # UDP・4E
   python scripts/clpa_client_conformance_driver.py --profile melsec:qcpu:qj71e71-100   # TCP・3E
   ```
4. 各試験項目について:
   - ツール GUI の「詳細設定/パラメータ設定」で**要求パターン(デバイス・点数・書込値)を確認**
   - ドライバの `run <id> k=v ...` でパターンどおりの要求を発行
     - 例: `run 1 device=W100 points=1`(一括読出し W100 1 ワード)
     - 例: `run 3 device=W1110 values=0x1102`(一括書込み)
     - 読出し系は 2 回実行して値の変化を確認する指示の項目がある(ガイド例: 1 回目 0102h / 2 回目 0000h)
   - ドライバが表示する**受信データ・終了コードを確認**し、ツールの「結果入力」に記入
5. 全項目完了 → 「テスト中断」 → 結果入力が全て PASS → **Step4 結果ログ出力**(CSV はツールと同じフォルダに出る)
6. 証跡(CSV・通信ログ)を `internal_docs/maintainer/conformance-results/` にコピーして保管

## 事前リハーサル(任意)

SlmpMockServer 相手に全項目の疎通を確認できる(2026-07-07 実施済み、下記結果):

```
cd D:\MockBuild\SlmpMockServer
python -m slmp_mock     # 別ターミナル。ポート 5010 が使用中なら config でポート変更
python scripts/clpa_client_conformance_driver.py --host 127.0.0.1 --port 5010 --run-all
```

- TCP×4E: 23/25 OK。パスワード 2 項目はモックに `plc.remote_password` を設定した構成で別途確認済み
  (ロック中 C201h → 1630 解除 → 正常応答 → 1631 ロック → C201h の実機挙動を再現)
- TCP×3E(qcpu:qj71e71-100): 23/25 OK(パスワード 2 項目は同上)
- UDP×4E: 22/25 OK。**項目 9(0802 モニタ)はモックの仕様で C05Ch**(モニタ登録が TCP セッション単位のため UDP では未登録扱い)。ドライバ側の問題ではない。ツール相手では要確認

## 注意事項

- リモートパスワード長は系列依存(iQ-R=6〜32 バイト / Q・L=4 バイト固定)。ドライバの `password=auto` がプロファイルに応じて選択する。ツールのパターンが指定する値がある場合は `run 24 password=XXXX` で上書き
- ラッチクリア(1005)は STOP 中のみ有効。ドライバの項目順(RUN→PAUSE→STOP→ラッチクリア→リセット)どおりに実行する
- ツールの試験方法欄に従い、要求のタイマ値は 0000h のまま変更しないこと

# refactor-instructions.md

plc-comm-slmp-python のリファクタリング指示書。
この文書は実装担当モデル向けの完結した作業指示である。実装前にこの文書全体を読むこと。

> **最重要の前提**: このパッケージは PyPI に公開済み(`slmp-connect-python` 0.1.15)であり、
> 実機 PLC(iQ-R / QnUDV / QCPU / QnU / iQ-L)での検証記録(`TODO.md`、`internal_docs/`、
> CHANGELOG)に紐づくワイヤフォーマット(SLMP バイナリ 3E/4E)を実装している。
> **公開 API・送信フレームのバイト列・エラーコード対応を 1 バイトたりとも変えてはならない。**
>
> 本リポジトリ最大の負債は「同じプロトコルオーケストレーションロジックが手書きで
> 3 系統(同期クライアント / 非同期クライアント / utils の sync・async ヘルパ対)に
> 複製されている」ことである。本タスクの中心は、この複製を**挙動を変えずに**縮め、
> ドリフト(片方だけ修正される事故)を防ぐ安全網を作ることである。
> 公開面の再設計・rename は目的ではなく禁止事項である。

---

## Objective

公開 API・ワイヤバイト列・クロススタック互換(.NET / Node-RED / Rust / C++ Minimal)を
一切壊さずに:

1. **sync/async のワイヤ同一性を固定する特性テストを追加する**(安全網。最優先)
2. **`client.py` / `async_client.py` の複製ロジックを共有の純粋関数へ抽出する**
   (ペイロード組立・応答デコード・バリデーション列を 1 箇所に)
3. **`utils.py` 内の async / `_sync` ヘルパ対の複製を同様に縮める**
4. (任意・承認後)`cli.py`(4,994 行・13 個の console-script 入口)の内部分割を**提案**する

「全面書き換え」「公開モジュールの rename」「API 整理」は行わない。

---

## Project Understanding

### 何のライブラリか

三菱電機 MELSEC PLC と SLMP(Seamless Message Protocol)バイナリ 3E/4E フレームで通信する
純 Python(依存ゼロ)クライアントライブラリ。TCP / UDP 対応。ASCII モードは意図的に対象外
(`TODO.md` 既知事項)。.NET 版(`plc-comm-slmp-dotnet`)/ Node-RED 版 / Rust 版 /
C++ Minimal 版と高レベル API の意味的互換を保つ(`TODO.md` の Cross-Stack API Alignment)。

### 利用者(壊すと影響が出る範囲)

1. **PyPI の一般利用者**(`pip install slmp-connect-python`)
2. **13 個の console-script**(`pyproject.toml` の `[project.scripts]`、すべて `slmp.cli:*_main`)
   と PyInstaller 製 CLI EXE(`run_ci.bat` 第 5 ステップ、`slmp.spec`)
3. **クロススタック検証フロー**: 5 スタック横並びの実機検証記録が本実装のフレームと対応する

### モジュール構成(slmp/、計約 14,800 行)

| ファイル | 行数 | 内容 |
|---|---|---|
| `cli.py` | 4,994 | 13 個の `*_main` 入口 + 実機検証スイープ・レポート生成(保守者向けツール群) |
| `client.py` | 1,811 | 同期 `SlmpClient`(TCP/UDP、約 60 メソッドのフラットなコマンド面) |
| `async_client.py` | 1,350 | `AsyncSlmpClient`(client.py とメソッド単位で手書きミラー) |
| `utils.py` | 1,286 | **文書化された推奨ユーザー面**: `open_and_connect` / `read_typed` / `read_named` / `poll` 等(async)+ 全てに `_sync` 双子 + read-plan 最適化 + `SlmpAddress` + `QueuedAsyncSlmpClient` |
| `core.py` | 1,081 | フレーム組立・デバイスエンコード・応答パースの純粋関数と型(共有基盤。健全) |
| `error_codes.py` | 2,078 | エンドコード表(データ。触らない) |
| `device_ranges.py` | 715 | デバイスレンジカタログ(データ + 少量ロジック) |
| `constants.py` / `errors.py` | 162 | 列挙・例外 |

### データフロー

ユーザーコード → `utils.py` の高レベルヘルパ(アドレス解析 → 型変換 → 最適 read-plan)
→ `SlmpClient` / `AsyncSlmpClient` のコマンドメソッド(バリデーション → `core.py` の
エンコーダでペイロード組立 → `request()`)→ TCP/UDP ソケット → 応答を `core.py` でパース。

### テスト(既存の安全網)

- `tests/test_slmp.py`(2,507 行): 同期クライアント中心の回帰(モックトランスポート)
- `tests/test_async_client.py`(312 行): 非同期側。**同期側より大幅に薄い**
- `tests/test_utils.py`(551 行)、`test_shared_spec.py` / `test_device_vectors.py`
  (クロススタック共有ベクトル)、`test_device_ranges.py` / `test_error_codes.py` ほか
- 実行: `python -m unittest discover -s tests -v`(`run_ci.bat` と同一)

### CI / 検証コマンド

`run_ci.bat`: ruff check → ruff format --check → mypy slmp → unittest discover →
PyInstaller EXE ビルド。GitHub Actions(`ci.yml`)も同系統。

---

## Behaviors To Preserve(絶対に壊さない既存挙動)

1. **公開 API**: `slmp/__init__.py` の import 一覧 + `slmp.client` / `slmp.async_client` /
   `slmp.utils` / `slmp.core` / `slmp.cli` というモジュールパス自体。既存の公開名の
   rename / 削除 / シグネチャ変更 / 既定値変更を一切しない。
2. **送信フレームのバイト列**: すべてのコマンドの組立結果。実機検証記録(TODO.md /
   internal_docs)との対応が本ライブラリの価値の根幹。
3. **console-script 入口**: `pyproject.toml` の `slmp.cli:*_main` 13 個と `slmp.spec`
   (PyInstaller)が参照する `slmp/cli.py` のパス。
4. **挙動仕様の固定事項**(TODO.md に根拠):
   - 混在ブロック書込(`1406`)の拒否挙動は仕様。フォールバック分割を勝手に入れない
   - `plc_family` が高レベル唯一の PLC セレクタ。低レベルのノブを公開面へ昇格しない
   - セマンティック原子性: 1 論理値・1 論理ブロックを暗黙分割しない
   - `*_raw` ラッパは保守者向け(ユーザー文書に出さない)
5. **警告・例外の文言と型**: `_warn_practical_device_path` / `_warn_boundary_behavior` 等の
   警告、`SlmpError` のメッセージ形式(テストとユーザーコードが依存しうる)。
6. **依存ゼロ**(`dependencies = []`)。実行時依存を追加しない。
7. **バージョン番号・CHANGELOG**: 本タスクで変更しない(下記 Stop And Ask の既知不一致を除き、報告のみ)。

---

## Non-Negotiables(交渉不可の制約)

- 最初に `git status` を確認する。未コミット変更があれば混ぜず、報告して停止する。
- 編集前に Baseline Commands をすべて実行し、結果(テスト件数含む)を記録する。
- 変更は小さく戻しやすい単位(1 コマンド群ずつ)。コミットはユーザーの指示があるまで行わない。
- 無関係な整形・「ついで」リファクタリングをしない。
- 新しい実行時依存・dev 依存を追加しない。`pyproject.toml` は変更しない
  (Phase 3 で `cli.py` を触る承認が出た場合のみ、entry-points の対応更新を例外とする)。
- 抽出した共有関数は**プライベートモジュール**(例: `slmp/_operations.py`)に置き、
  `__init__.py` から export しない。
- 既存テストの既存アサーションを変更しない(追加のみ可)。
- 実機 PLC への接続を行わない(テストは全てモック)。
- 正しさが不明な場合は実装を止め、「Stop And Ask」として質問を報告書に書く。

---

## Stop And Ask Conditions(即時停止して質問する条件)

- **Phase 1 のワイヤ同一性テストで sync と async の出力バイト列が食い違った**
  (= 既にドリフトが起きている)。どちらが正かは実機検証記録に紐づくため、
  **勝手に直さず**両者のバイト列を併記して質問する。
- `utils.py` の async 版と `_sync` 版でロジックが食い違っているのを見つけた(同上)。
- 既存テストが自分の変更後に落ちた ⇒ 即座に巻き戻して報告。
- 公開名・モジュールパス・警告文言・例外型の変更が必要に見えた。
- `pyproject.toml` の `version = "0.1.15"` と `slmp/__init__.py` の
  `__version__ = "0.1.14"` の不一致(**調査時点で確認済みの既知問題**)。
  リリースメタデータなので修正せず、報告書に記載して人間の判断を仰ぐ。
- `cli.py` の分割(Phase 3)に着手してよいかの承認が得られていない。
- 本書の Debt Map に無い大きな問題を発見した(報告のみ)。

---

## Baseline Commands

作業ディレクトリ: リポジトリルート。Python 3.10+。Windows 前提(`run_ci.bat`)だが、
個別コマンドは OS を問わない。実機 PLC 不要・接続禁止。

```bash
git status                                   # クリーンであることを確認
python -m ruff check .
python -m ruff format --check .
python -m mypy slmp
python -m unittest discover -s tests -v     # テスト件数を記録すること
```

PyInstaller ビルド(`run_ci.bat` 第 5 ステップ)は環境に PyInstaller がある場合のみ実行し、
無ければ「未実施」と報告書に明記する。

---

## Debt Map

行番号は調査時点(main, commit `21b1e8c`)のアンカー。ドリフトしていたら宣言名で探すこと。

### D1. sync/async ワイヤ同一性の特性テスト不在 【実装可 / 最優先】

- **根拠**: `tests/test_async_client.py` は 312 行で、同期側(`test_slmp.py` 2,507 行)に
  比べ大幅に薄い。両クライアントは手書きミラーなのに「同じ呼び出しで同じバイト列を送る」
  ことを機械的に保証するテストが無い。
- **なぜ負債か**: D2 のリファクタリングを安全に行う前提が無い。また現状でも片側だけの
  修正(ドリフト)を検出できない。
- **改善案**: モックトランスポート(送信バイト列を記録し、固定応答を返す)を sync / async
  共通で用意し、主要コマンド(read/write devices・dword・float・random・block・monitor・
  remote 系・label 系・memory/extend/cpu_buffer 系)について
  「`SlmpClient` と `AsyncSlmpClient` が同一引数で**同一の送信バイト列**を生成する」ことを
  比較する特性テストを `tests/test_sync_async_parity.py` として追加する。
  期待値は手書きせず、**現在の実装出力同士の比較**にする(どちらが正かを判断しない)。
- **検証**: 追加テストを含め全テストが通ること。
- **リスク**: 低(テスト追加のみ)。

### D2. `client.py` / `async_client.py` の約 60 メソッドの手書き複製 【実装可 / 主作業】

- **根拠**: 例として `read_devices` は `client.py:331-377` と `async_client.py:336-360` で
  バリデーション・subcommand 解決・ペイロード組立・応答デコードが行単位で同一。
  `write_devices` / dword / float / random / block / monitor / remote / label /
  memory / extend_unit / cpu_buffer 系もすべて同型。
- **なぜ負債か**: 機能追加・修正のたびに 2 箇所(utils を含めると最大 4 箇所)を同期更新する
  必要があり、ドリフト事故の温床。実際に薄い async テストでは検出できない。
- **改善案**: 「リクエスト組立(引数 → コマンド/サブコマンド/ペイロードのバイト列)」と
  「応答デコード(バイト列 → 戻り値)」を**await を含まない純粋関数**として
  `slmp/_operations.py`(新規・非公開)へ抽出し、両クライアントのメソッド本体を
  `payload = _operations.build_read_devices(...)` → `request(...)` →
  `return _operations.decode_read_devices(...)` の薄い形に置き換える。
  - 1 コマンド群ずつ(read 系 → write 系 → random → block → …)行い、各群ごとに全テスト実行
  - 警告呼び出し(`_warn_*`)・例外文言の発生順序も変えない
  - D1 のパリティテストが**変更前後で同じバイト列**を保証する
- **影響範囲**: `client.py` / `async_client.py` 全体。公開シグネチャは不変。
- **リスク**: 中。必ず D1 完了後に着手。
- **検証**: 全テスト + パリティテスト。`git diff` で公開メソッドのシグネチャ変更が
  無いことを確認。

### D3. `utils.py` の async / `_sync` ヘルパ対の複製 【実装可(D2 の後)】

- **根拠**: `read_typed`(174 行)と `read_typed_sync`(270 行)は分岐構造まで完全同一。
  `write_typed` / `write_bit_in_word` / `read_named` / `poll` / single_request /
  chunked 系すべてに `_sync` 双子が存在する。
- **なぜ負債か**: D2 と同じドリフト構造。`utils.py` は文書化された推奨ユーザー面なので
  事故の影響が最も大きい。
- **改善案**: 型変換・プラン決定(どのコマンドを何点読むか)を純粋関数へ抽出し、
  async / sync は「実行だけ」を担う薄い関数にする。`_compile_read_plan` は既に純粋なので
  方針の手本になる。**公開名(`read_typed` / `read_typed_sync` 等)と挙動は不変。**
- **リスク**: 中。1 ヘルパ対ずつ。
- **検証**: `test_utils.py` + 全テスト。

### D4. `cli.py` 4,994 行の単一モジュール 【提案のみ / 承認が出た場合に限り実装】

- **根拠**: 13 個の `*_main` 入口、レポート生成(Markdown/JSON)、互換マトリクス描画、
  named-target 解析などが 1 ファイルに同居。
- **なぜ負債か**: 保守者向け検証ツールとして肥大を続けており、テストもほぼ無い。
  ただし**ライブラリ本体の品質には直接影響しない**。
- **改善案(提案)**: `slmp/cli.py` を façade として残し(`*_main` の re-export)、実体を
  `slmp/_cli/` サブパッケージへ move-only 分割する。`pyproject.toml` の entry-points と
  `slmp.spec` の参照は不変で済む。**ただし `slmp.cli` がユーザー向け公開面か保守者専用かの
  製品判断が必要なため、承認が出るまで実装しない。**
- **検証(実施時)**: 全 console-script の `--help` 実行 + PyInstaller ビルド。

### D5. バージョン不一致 【報告のみ】

- `pyproject.toml` = 0.1.15、`slmp/__init__.py.__version__` = 0.1.14。
  リリースメタデータのため修正はせず報告書に記載(Stop And Ask 参照)。

### D6. その他(現状維持 / 報告のみ)

- `core.py` は純粋関数の共有基盤として健全。D2 の抽出先候補として拡張する場合も
  既存関数は変更しない。
- `error_codes.py` / `device_ranges.py` はデータ主体。触らない。
- `test_slmp.py` 2,507 行の単一テストファイルは読みにくいが、**分割はテスト資産の
  改変リスクの方が大きい**ため本タスクでは行わない(提案として報告可)。

---

## Implementation Phases

### Phase 0: 現状確認

1. `git status` 確認(クリーンでなければ停止・報告)
2. Baseline Commands を実行し、結果(テスト件数)を記録

### Phase 1: 安全網(D1)

1. sync/async 共通のモックトランスポートを `tests/` 内に実装
2. コマンド群ごとにパリティテストを追加(期待値は実装出力同士の比較)
3. **食い違いが出たコマンドは Stop And Ask に記録**し、そのコマンドを D2 の対象から外す
4. 全テスト実行

### Phase 2: クライアント複製の抽出(D2)

1. read 系 → write 系 → dword/float → random → block → monitor → remote →
   label → memory/extend/cpu_buffer の順に、1 群ずつ `slmp/_operations.py` へ抽出
2. 各群ごとに: 全テスト + パリティテスト + `mypy` + `ruff`
3. 1 群でも想定外(状態依存・順序依存)が出たらその群をスキップして報告

### Phase 3: utils ヘルパ対の縮約(D3)

1. `read_typed` 対 → `write_typed` 対 → `write_bit_in_word` 対 → `read_named` 対 →
   single_request/chunked 系の順に 1 対ずつ
2. 各対ごとに全テスト実行

### Phase 4: cli.py(D4)

承認が無い限り実装しない。提案(分割案の目次レベル)を報告書に書くのみ。

### Phase 5: 検証と報告

1. 全 Verification Requirements を最終実行
2. Reporting Format に従って報告書を作成

---

## Verification Requirements

各フェーズ完了時に最低限:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy slmp
python -m unittest discover -s tests -v
```

最終フェーズでは追加で:

- テスト件数が baseline から**増えている**こと(D1 追加分)。減っていたら失敗。
- `git diff` で以下を確認:
  - `slmp/__init__.py` に変更が無い(または import 元の機械的変更のみ)
  - 公開メソッドのシグネチャ・docstring の意味内容に変更が無い
  - `pyproject.toml` / `slmp.spec` / `CHANGELOG.md` に変更が無い
- 環境があれば PyInstaller ビルド(`run_ci.bat` 第 5 ステップ相当)。無ければ未実施と明記。

---

## Reporting Format

作業完了時(または中断時)に以下を Markdown で報告する:

1. **Baseline 結果**: 実行コマンドと結果(テスト件数)
2. **D1 パリティ表**: コマンド群 × パリティテスト有無 × 結果(一致 / 食い違い / 未対応)
3. **D2/D3 の抽出一覧**: 移動した関数と移動先、群ごとのテスト結果
4. **食い違い・バージョン不一致**: 発見した場合は両者の値を併記(修正はしない)
5. **D4 の提案**: cli.py 分割案(実装はしない)
6. **各フェーズの検証結果**: 最後に実行したコマンドと結果(失敗を隠さない)
7. **Stop And Ask**: 発生した質問と停止範囲
8. **未実施事項**: PyInstaller 未実施等の明記

---

## Out-of-scope Items(やらないこと)

- 公開 API・モジュールパス・公開名の変更/追加/整理(`slmp.utils` の rename を含む)
- 送信フレームバイト列・警告文言・例外型/文言の変更(食い違いを見つけても報告のみ)
- `utils.py` → `high_level.py` のような「分かりやすさのための rename」(提案のみ可)
- 混在ブロック書込のフォールバック等、セマンティクスに関わる機能変更
- バージョン番号変更、`CHANGELOG.md` 更新、PyPI への公開
- 依存追加、`pyproject.toml` 変更(D4 承認時の entry-points 対応更新を除く)
- `error_codes.py` / `device_ranges.py` のデータ変更
- `tests/test_slmp.py` の分割・既存アサーション変更
- `docsrc/` / `internal_docs/`(実機検証記録)の変更
- 実機 PLC を使う検証
- 兄弟リポジトリ(dotnet / nodered / rust / cpp 一族)の変更

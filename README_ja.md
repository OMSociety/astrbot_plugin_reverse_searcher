<p align="center"><a href="README.md">中文</a> · <a href="README_en.md">English</a> · <a href="README_ru.md">Русский</a> · <strong>日本語</strong></p>

<div align="center">

<img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_reverse_searcher/main/logo.png" width="120" alt="ReverseSearcher Logo" />

# 逆画像検索アシスタント

**5 つのエンジンによる逆画像検索** —— AnimeTrace でキャラ判定 · SauceNAO で出典特定 · Google Lens で総合フォロー · Yandex で類似画像検索 · E-Hentai で同人誌検索

[![Version](https://img.shields.io/badge/version-1.1.1-blue.svg)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/OMSociety/astrbot_plugin_reverse_searcher)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/stargazers)
[![Issues](https://img.shields.io/github/issues/OMSociety/astrbot_plugin_reverse_searcher)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/issues)

</div>

> 本プロジェクトは AI によって作成され、ソースコードの一部は [astrbot_plugin_img_rev_searcher_Ver2](https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2) を基にしています

---

## 主な特徴

| 特徴 | 説明 |
|------|------|
| **5 つの検索エンジン** | AnimeTrace はキャラ判定、SauceNAO は出典特定、Google Lens は総合バックアップ、Yandex は類似画像検索、E-Hentai は同人誌検索と、それぞれ役割分担 |
| **キーワードトリガー** | `以图搜图`（画像検索）と画像を送るだけで検索でき、エンジンの別名（`a`/`s`/`e`/`g`/`y`）で素早く指定可能 |
| **LLM による自律検索** | ボットが会話の意図から検索の要否と使用エンジンを自主的に判断。手動コマンド不要 |
| **インテントルーティング** | キーワードの重み付きマッチングで最適なエンジンを自動選択。「これ誰」と言えば自動で AnimeTrace を使用 |
| **美しい結果カード** | 検索結果をモダンなカード画像としてレンダリング（エンジンカラーのグラデーションヘッダー、類似度のカラーバッジ、AI 検出ラベル）。クラウドのテキスト画像化サービスに接続できない場合は自動で PIL にフォールバック |
| **マルチエンジン自由切り替え** | エンジンは必要に応じて有効/無効化でき、失敗時は原因を表示し、別のエンジンで手動で再検索できます |

---

## 機能概要

### 検索カードのレンダリング
検索完了後、カード画像を自動生成。元画像と結果サムネイルを同じ画面に並べ、類似度がひと目でわかります:

<img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_reverse_searcher/main/docs/search_example.png" alt="検索結果カードの例" width="480" />

### キーワードトリガー
`以图搜图` に画像を添えて送信（または引用メッセージへの返信）すると、ガイドに沿って検索できます:

```
ユーザー: 以图搜图
🤖 → エンジン紹介カードを送信しました。エンジンを選択してください
ユーザー: a この画像
🤖 → AnimeTrace を選択しました。検索中...
     → 検索結果カードを送信 ✅
```

### LLM による自律検索
ボットには `reverse_search` ツールが組み込まれており、会話内容から検索の要否を自律的に判断します:

```
ユーザー: フラン、この画像のキャラクターは誰？
🤖 → reverse_search(intent=キャラ特定)
    🔍 [AnimeTrace] 3 件の結果が見つかりました
    キャラクター: フランドール・スカーレット | 作品: 東方Project...
```

### インテントルーティング
エンジンを指定しなくても、意図を伝えるだけで自動選択:

| 意図 | 自動ルーティング |
|------|---------|
| 「これ誰 / どのキャラ / コスプレ」 | → AnimeTrace |
| 「出典探し / 作者探し / pixiv pid」 | → SauceNAO |
| 「類似画像探し / これに似てる」 | → Yandex |
| 「同人誌探し / 二次創作」 | → E-Hentai |
| 「元画像探し / 総合検索」 | → Google |

---

## クイックスタート

### ステップ 1: インストール

AstrBot WebUI → プラグインマーケット → `astrbot_plugin_reverse_searcher` を検索

### ステップ 2: 最小構成（インストールするだけですぐ使える）

キー不要の 3 エンジン AnimeTrace・Yandex・E-Hentai は**設定不要**で利用可能:

1. AstrBot 再起動後、`以图搜图` + 画像を送るだけ
2. またはボットに「このキャラは誰？」と話しかければ LLM が自動で検索

> **ヒント：**任意の拡張: SauceNAO の `api_key`（[申請ページ](https://saucenao.com/user.php)）を設定するとイラストレーター/出典検索が利用可能に。Google エンジンには [SerpAPI Key](https://serpapi.com/) が必要。ExHentai には有効な Cookie が必要です。

### 依存関係のインストール
プラグインは `httpx`、`Pillow`、`pyquery` などに依存します。AstrBot がプラグインのインストール時に自動で処理します。

---

## 対応検索エンジン

| エンジン | 説明 | 必要な設定 |
|:----|:----|:----|
| **animetrace** | アニメキャラ認識（最強）。作品名 + キャラ名を返す | 設定不要 |
| **yandex** | 類似画像検索 | Cookie 推奨（Yandex はボット対策が厳しく、未設定では CAPTCHA や結果なしになる場合あり） |
| **ehentai** | E-Hentai 同人誌検索 | 設定不要（ExHentai には Cookie が必要） |
| **saucenao** | 総合出典検索。Pixiv イラストの第一候補 | `api_key` 推奨 |
| **google** | Google Lens 総合フォロー | SerpAPI Key が必要 |

---

## 設定項目の説明

### トップレベル設定

| 設定項目 | 型 | デフォルト | 説明 |
|--------|------|------|------|
| `enable_keyword_trigger` | bool | `true` | キーワードトリガーの有効/無効。無効時は LLM ツールのみ使用可能 |
| `proxies` | string | `""` | プロキシアドレス。例: `http://127.0.0.1:7890`（中国本土からのアクセスには必須） |
| `allow_third_party_image_host` | bool | `true` | ローカル画像をサードパーティの一時画像ホストへアップロードすることを許可するか（Google/Yandex のローカル画像検索に必要。無効化するとこの 2 エンジンではローカル画像検索不可） |

### タイムアウト設定 `timeout_settings`

| 設定項目 | 型 | デフォルト | 説明 |
|--------|------|------|------|
| `search_params_timeout` | int | `30` | ユーザーによるエンジン/画像の追加入力の待機タイムアウト（秒） |

### キーワード `keyword`

| 設定項目 | 型 | デフォルト | 説明 |
|--------|------|------|------|
| `trigger_keywords` | list | `["以图搜图", "image search"]` | 検索をトリガーするキーワードのリスト |
| `engine_keywords` | object | `a/s/e/g/y` | 各エンジンのカスタム別名（animetrace=`a`、saucenao=`s`、ehentai=`e`、google=`g`、yandex=`y`） |

> **ヒント：**トリガーはどの言語でも設定できます。英語圏向けに `"image search"` を追加するのも有効です。

### エンジンの有効化 `available_apis`

| 設定項目 | 型 | デフォルト | 説明 |
|--------|------|------|------|
| `animetrace` / `ehentai` / `google` / `yandex` / `saucenao` | bool | `true` | 各エンジンの有効/無効スイッチ |

### エンジンのデフォルトパラメータ `default_params`

| 設定項目 | 説明 |
|--------|------|
| `animetrace.model` | 認識モデル。デフォルトは `full_game_model_kira` |
| `animetrace.is_multi` / `ai_detect` | 複数キャラ検索 / AI 検出スイッチ |
| `ehentai.is_ex` / `covers` / `similar` / `exp` | ExHentai スイッチ、カバー/類似/実験的モード |
| `ehentai.cookies` | **E-Hentai の Cookie**（ExHentai に必須。取得方法はよくある質問 Q5 を参照） |
| `google.serpapi_key` / `zenserp_key` | SerpAPI（推奨）/ Zenserp（予備）のキー |
| `google.hl` / `country` / `max_results` | 言語 / 地域 / 最大結果数 |
| `saucenao.api_key` / `minsim` / `numres` | API Key / 最低類似度 / 結果数 |
| `yandex.max_results` / `use_ru_fallback` | 結果数 / `.ru` ドメインへのフォールバック |
| `yandex.cookies` | **Yandex の Cookie**（ボット対策が厳しく、未記入だと CAPTCHA で結果なしになる可能性あり。取得方法は Q5 を参照） |

> **プライバシーに関する開示: ローカル画像はサードパーティの画像ホストへアップロードされます** —— **ローカル画像**で **Google / Yandex** を検索する場合、プラグインは画像をまず一時画像ホスト（`tmpfiles.org` / `uguu.se` / `litterbox.catbox.moe` / `tmp.ninja`）へアップロードし、URL 形式で検索する必要があります。**つまり、あなたの画像は公開の一時画像ホストへアップロードされます**。保持期間はサードパーティが決めます。無効化するには `allow_third_party_image_host` を `false` に設定してください（この場合、この 2 エンジンではローカル画像検索ができず、画像 URL の使用か他のエンジンへの切り替えが必要です）。

### クイック設定テンプレート

```json
{
  "enable_keyword_trigger": true,
  "proxies": "",
  "allow_third_party_image_host": true,
  "timeout_settings": {
    "search_params_timeout": 30
  },
  "keyword": {
    "trigger_keywords": ["以图搜图", "image search"],
    "engine_keywords": { "animetrace": "a", "ehentai": "e", "google": "g", "yandex": "y", "saucenao": "s" }
  },
  "available_apis": { "animetrace": true, "ehentai": true, "google": true, "yandex": true, "saucenao": true },
  "default_params": {
    "animetrace": { "model": "full_game_model_kira", "is_multi": false, "ai_detect": false },
    "ehentai": { "is_ex": false, "covers": false, "similar": true, "exp": false, "cookies": "" },
    "google": { "serpapi_key": "", "zenserp_key": "", "hl": "zh-CN", "country": "HK", "max_results": 10 },
    "saucenao": { "api_key": "", "hide": 3, "numres": 5, "minsim": 30, "output_type": 2 },
    "yandex": { "max_results": 10, "use_ru_fallback": true, "cookies": "" }
  }
}
```

---

## LLM が呼び出せるツール

プラグインは 2 つの LLM ツールを登録しており、ボットが呼び出しタイミングを自律的に判断します:

```
ユーザー: この画像は何のキャラクター？
🤖 → reverse_search(intent=キャラ特定)
    🔍 [AnimeTrace] 3 件の結果が見つかりました
    キャラクター: フランドール・スカーレット | 作品: 東方Project...

ユーザー: SauceNAO でこの画像のイラストレーターを調べて
🤖 → reverse_search_with_engine(engine=saucenao)
    🔍 [SauceNAO] 5 件の結果が見つかりました
    Pixiv: イラストレーター KuroNeko | 類似度 95.2%
```

### reverse_search
汎用画像検索ツール。意図に応じてエンジンを自動選択します。

| パラメータ | 型 | 説明 |
|------|------|------|
| `image_base64` | string? | 画像の base64 エンコード（URL とどちらか一方） |
| `image_url` | string? | 画像の URL（base64 とどちらか一方） |
| `intent` | string? | 検索意図（例:「キャラ特定」「出典特定」「類似画像探し」）。エンジン自動選択に使用 |

### reverse_search_with_engine
エンジンを指定して検索。ユーザーが特定のエンジンを明示的に要求した場合に呼び出します。

| パラメータ | 型 | 説明 |
|------|------|------|
| `image_base64` / `image_url` | string? | 画像のソース（どちらか一方） |
| `engine` | string | **必須**。エンジン名: `animetrace` / `saucenao` / `ehentai` / `google` / `yandex` |

---

## よくある質問

### Q1: API Key が必要なエンジンは？

| エンジン | 必要な設定 |
|------|---------|
| AnimeTrace / Yandex / E-Hentai | 不要。インストールするだけですぐ使える |
| SauceNAO | `api_key` 推奨（[無料申請](https://saucenao.com/user.php)、1 日 150 回まで） |
| Google | [SerpAPI Key](https://serpapi.com/)（推奨）または Zenserp Key が必要 |

### Q2: E-Hentai で検索できない / ExHentai のコンテンツを見たい？

- E-Hentai は設定なしで検索可能。**ExHentai** にはアカウントの Cookie（`ipb_member_id`、`ipb_pass_hash`、`igneous`）が必要で、`default_params.ehentai.cookies` に入力し、`is_ex` を有効化してください

### Q3: 中国本土のサーバーで検索が遅い / 検索できない？

`proxies` にプロキシを設定してください（例: `http://127.0.0.1:7890`）。SauceNAO・Google・Yandex などのエンジンは中国本土の IP に対してリスク制御を行うため、プロキシは必須です。

### Q4: 検索結果カードの画像が生成されない？

プラグインはまず AstrBot のクラウド text-to-image（t2i）で HTML カードをレンダリングします。クラウドサービスに接続できない場合/タイムアウト時は**内蔵の PIL レンダリングへ自動フォールバック**（画像は生成されます）。両方失敗した場合のみプレーンテキストにフォールバックします。AstrBot を最新版にアップグレードするとクラウドレンダリングの安定性が向上します。

### Q5: Yandex / E-Hentai の Cookie の取得方法と入力内容は？

Cookie とは、ブラウザがサイトへのログイン後に自動保存する認証情報のことです。入力するのは **`name1=value1; name2=value2` 形式の文字列 1 行全体**です。取得方法は 2 通りあります（どちらかを選択）:

**方法 1: コンソールで 1 発取得（最も簡単。まずはこれを試してください）**
1. ブラウザで対象サイトにアクセスし、**ログイン**します（E-Hentai は https://e-hentai.org、ExHentai は https://exhentai.org、Yandex は https://yandex.com/images）
2. **F12** を押す → 上部の **Console（コンソール）** タブをクリック
3. 下部の入力欄に `document.cookie` と入力し **Enter** を押す
4. コンソールに Cookie 文字列 1 行がそのまま出力される → **それをコピー**（`ipb_member_id=123; ipb_pass_hash=abc; ...` のような形式）
5. 制限: **HttpOnly** のフィールドはこの方法では取得できません —— **E-Hentai ならこれで十分**。**Yandex は重要フィールドの一部が HttpOnly のため、方法 2 を推奨**

**方法 2: Network パネル（完全版。Yandex はこちらを推奨）**
1. 対象サイトにログインした状態で **F12** を押す → **Network（ネットワーク）** タブをクリック
2. **注意: 上部のフィルター入力欄には何も入力しないでください**（入力するとリクエストが絞り込まれ、リストが空になります！）。空のままにしておく
3. **ページを再読み込み**（F5）→ 左側にリクエスト一覧が表示される → **最初のリクエストをクリック**
4. 右側で **Headers（ヘッダー）** を開く → 下へスクロールして **Request Headers（リクエストヘッダー）** を探す
5. **`Cookie:`** で始まる行を見つける → **行全体をコピー**（`Cookie:` の後ろの内容すべて）

コピーした内容は次のような形式です（値は実際のものによります）:
```
yandexuid=1587138991653; ymex=1986384493.yrts.159; Session_id=3:163...:0
```
行全体をプラグイン設定の `default_params.yandex.cookies` / `default_params.ehentai.cookies` に貼り付ければ完了です。

> **ヒント：**Yandex はボット対策が厳しく、Cookie 未記入だと CAPTCHA が発生して検索結果が得られない場合があります。E-Hentai で ExHentai のコンテンツを検索するには Cookie が必須です（`ipb_member_id`、`ipb_pass_hash`、`igneous` の 3 つの重要フィールドを含む）。プラグインが実際にリクエストするドメイン（yandex.com）から取得するのが最も確実です。

## 更新履歴

> **[更新履歴を見る →](CHANGELOG.md)**

## 応援と謝辞

このプラグインが役に立ったら、Star をお願いします。問題や提案があれば [Issue](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/issues) または [Pull Request](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/pulls) へお寄せください。

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) オープンソースのチャットボットフレームワーク
- [astrbot_plugin_img_rev_searcher_Ver2](https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2) オリジナルプロジェクト

## ライセンスと作者

本プロジェクトは **AGPL-3.0** で公開されています。

[@OMSociety](https://github.com/OMSociety)

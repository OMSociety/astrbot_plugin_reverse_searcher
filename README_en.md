<p align="center"><strong>English</strong> · <a href="README.md">中文</a> · <a href="README_ru.md">Русский</a> · <a href="README_ja.md">日本語</a></p>

<div align="center">

<img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_reverse_searcher/main/logo.png" width="120" alt="ReverseSearcher Logo" />

# Reverse Image Search Assistant

**Reverse image search powered by five engines** — AnimeTrace recognizes characters · SauceNAO finds the source · Google Lens as the catch-all · Yandex finds similar images · E-Hentai searches doujinshi

[![Version](https://img.shields.io/badge/version-1.1.1-blue.svg)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/OMSociety/astrbot_plugin_reverse_searcher)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/stargazers)
[![Issues](https://img.shields.io/github/issues/OMSociety/astrbot_plugin_reverse_searcher)](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/issues)

</div>

> This project was written by AI; part of the source code is based on [astrbot_plugin_img_rev_searcher_Ver2](https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2)

---

## Key Features

| Feature | Description |
|------|------|
| **Five search engines** | AnimeTrace recognizes characters, SauceNAO finds the source, Google Lens serves as the comprehensive fallback, Yandex finds similar images, and E-Hentai searches doujinshi — each with its own role |
| **Keyword trigger** | Send `以图搜图` (reverse image search) plus an image to search; engine aliases (`a`/`s`/`e`/`g`/`y`) allow quick engine selection |
| **LLM-driven search** | The bot decides on its own when to search and which engine to use based on conversational intent — no manual commands needed |
| **Intent routing** | Automatically picks the best engine via weighted keyword matching — say "who is this" and AnimeTrace is selected |
| **Beautiful result cards** | Search results are rendered as modern card images (engine-colored gradient header, colorful similarity badges, AI-detection labels); automatically falls back to PIL when the cloud text-to-image service is unreachable |
| **Free multi-engine switching** | Enable/disable engines as needed; on failure the reason is reported and you can retry with another engine |

---

## Feature Overview

### Search card rendering
After a search completes, a card image is generated automatically: the source image and result thumbnails side by side, with similarity at a glance:

<img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_reverse_searcher/main/docs/search_example.png" alt="search result card example" width="480" />

### Keyword trigger
Send `以图搜图` with an image (or reply to a quoted message) and follow the prompts to complete the search:

```
User: image search
🤖 → Sending engine intro card, please choose an engine
User: a this image
🤖 → AnimeTrace selected, searching...
     → Sending search result card ✅
```

### LLM-driven search
The bot has a built-in `reverse_search` tool and decides on its own whether to search based on the conversation:

```
User: Flandre, tell me which character is in this image
🤖 → reverse_search(intent=identify character)
    🔍 [AnimeTrace] Found 3 results
    Character: Flandre Scarlet | Series: Touhou Project...
```

### Intent routing
No need to specify an engine — just state your intent and one is chosen automatically:

| Intent | Auto route |
|------|---------|
| "Who is this / which character / cos" | → AnimeTrace |
| "Find the source / find the artist / pixiv pid" | → SauceNAO |
| "Find similar images / looks like this" | → Yandex |
| "Find doujinshi / fan works" | → E-Hentai |
| "Find the original / general search" | → Google |

---

## Quick Start

### Step 1: Installation

AstrBot WebUI → Plugin marketplace → search for `astrbot_plugin_reverse_searcher`

### Step 2: Minimal configuration (works out of the box)

**No configuration required** to use the three key-free engines AnimeTrace, Yandex, and E-Hentai:

1. After restarting AstrBot, simply send `以图搜图` + an image
2. Or just tell the bot "help me find out who this character is" and let the LLM search automatically

> **Note:** Optional enhancements: configure the SauceNAO `api_key` ([apply here](https://saucenao.com/user.php)) to unlock artist/source search; the Google engine requires a [SerpAPI Key](https://serpapi.com/); ExHentai requires a valid Cookie.

### Dependencies
The plugin depends on `httpx`, `Pillow`, `pyquery`, etc.; AstrBot handles these automatically when installing the plugin.

---

## Supported Search Engines

| Engine | Description | Configuration |
|:----|:----|:----|
| **animetrace** | Anime character recognition (the strongest); returns work title + character name | None needed |
| **yandex** | Similar image search | Cookie recommended (Yandex has strict anti-scraping; without it you may get CAPTCHA or no results) |
| **ehentai** | E-Hentai doujinshi search | None needed (ExHentai requires a Cookie) |
| **saucenao** | General source search; first choice for Pixiv illustrations | `api_key` recommended |
| **google** | Google Lens catch-all | Requires a SerpAPI Key |

---

## Configuration Reference

### Top-level settings

| Option | Type | Default | Description |
|--------|------|------|------|
| `enable_keyword_trigger` | bool | `true` | Keyword trigger switch; when disabled, only the LLM tools are available |
| `proxies` | string | `""` | Proxy address, e.g. `http://127.0.0.1:7890` (required for access from mainland China) |
| `allow_third_party_image_host` | bool | `true` | Whether to allow uploading local images to third-party temporary image hosts (needed for local-image search on Google/Yandex; when disabled, these two engines cannot search local images) |

### Timeout settings `timeout_settings`

| Option | Type | Default | Description |
|--------|------|------|------|
| `search_params_timeout` | int | `30` | Timeout (in seconds) for waiting for the user to supply an engine/image |

### Keywords `keyword`

| Option | Type | Default | Description |
|--------|------|------|------|
| `trigger_keywords` | list | `["以图搜图", "image search"]` | List of keywords that trigger a search |
| `engine_keywords` | object | `a/s/e/g/y` | Custom aliases per engine (animetrace=`a`, saucenao=`s`, ehentai=`e`, google=`g`, yandex=`y`) |

> **Note:** Any-language custom triggers work, e.g. add `"image search"` for English users.

### Engine switches `available_apis`

| Option | Type | Default | Description |
|--------|------|------|------|
| `animetrace` / `ehentai` / `google` / `yandex` / `saucenao` | bool | `true` | On/off switch for each engine |

### Engine default parameters `default_params`

| Option | Description |
|--------|------|
| `animetrace.model` | Recognition model, default `full_game_model_kira` |
| `animetrace.is_multi` / `ai_detect` | Multi-character search / AI detection switches |
| `ehentai.is_ex` / `covers` / `similar` / `exp` | ExHentai switch; cover/similar/experimental modes |
| `ehentai.cookies` | **E-Hentai Cookie** (required for ExHentai; see FAQ Q5 for how to obtain it) |
| `google.serpapi_key` / `zenserp_key` | SerpAPI (recommended) / Zenserp (fallback) keys |
| `google.hl` / `country` / `max_results` | Language / region / maximum number of results |
| `saucenao.api_key` / `minsim` / `numres` | API key / minimum similarity / number of results |
| `yandex.max_results` / `use_ru_fallback` | Number of results / `.ru` domain fallback |
| `yandex.cookies` | **Yandex Cookie** (strict anti-scraping; without it you may get a CAPTCHA and no results; see Q5 for how to obtain it) |

> **Privacy notice: local images are uploaded to third-party image hosts** — when searching **Google / Yandex** with **local images**, the plugin must first upload the image to a temporary image host (`tmpfiles.org` / `uguu.se` / `litterbox.catbox.moe` / `tmp.ninja`) and then search by URL. **This means your image will be uploaded to a public temporary image host**, and how long it is retained is decided by the third party. To disable this, set `allow_third_party_image_host` to `false` (in that case these two engines cannot search local images; use an image URL or switch to another engine instead).

### Quick configuration template

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

## LLM-Callable Tools

The plugin registers 2 LLM tools; the bot decides on its own when to call them:

```
User: What character is in this image?
🤖 → reverse_search(intent=identify character)
    🔍 [AnimeTrace] Found 3 results
    Character: Flandre Scarlet | Series: Touhou Project...

User: Use SauceNAO to find the artist of this image
🤖 → reverse_search_with_engine(engine=saucenao)
    🔍 [SauceNAO] Found 5 results
    Pixiv: Artist KuroNeko | Similarity 95.2%
```

### reverse_search
General-purpose image search tool; picks an engine automatically based on the intent.

| Parameter | Type | Description |
|------|------|------|
| `image_base64` | string? | Base64-encoded image (either this or a URL) |
| `image_url` | string? | Image URL (either this or base64) |
| `intent` | string? | Search intent (e.g. "identify the character", "find the source", "find similar images"), used to pick the engine automatically |

### reverse_search_with_engine
Search with a specified engine; called when the user explicitly requests a particular engine.

| Parameter | Type | Description |
|------|------|------|
| `image_base64` / `image_url` | string? | Image source (either one) |
| `engine` | string | **Required**, engine name: `animetrace` / `saucenao` / `ehentai` / `google` / `yandex` |

---

## FAQ

### Q1: Which engines need an API Key?

| Engine | Configuration |
|------|---------|
| AnimeTrace / Yandex / E-Hentai | None — works out of the box |
| SauceNAO | `api_key` recommended ([free registration](https://saucenao.com/user.php), 150 requests per day) |
| Google | Requires a [SerpAPI Key](https://serpapi.com/) (recommended) or a Zenserp Key |

### Q2: E-Hentai search fails / want to browse ExHentai content?

- E-Hentai searches with no configuration; **ExHentai** requires an account Cookie (`ipb_member_id`, `ipb_pass_hash`, `igneous`), filled into `default_params.ehentai.cookies`, with `is_ex` enabled

### Q3: Searches are slow / fail on servers in mainland China?

Configure a proxy in `proxies` (e.g. `http://127.0.0.1:7890`). Engines such as SauceNAO, Google, and Yandex apply risk controls to mainland Chinese IPs, so a proxy is essential.

### Q4: The result card image isn't generated?

The plugin prefers AstrBot's cloud text-to-image (t2i) service to render HTML cards; if the cloud service is unreachable or times out, it **automatically falls back to built-in PIL rendering** (an image is still produced). Only if both fail does it fall back to plain text. Upgrading AstrBot to the latest version improves cloud rendering stability.

### Q5: How do I get the Yandex / E-Hentai Cookie, and what do I paste in?

A Cookie is a credential your browser automatically saves after you log in to a website. What you need to paste is **one entire line in `name1=value1; name2=value2` format**. Two ways to get it (choose either):

**Method 1: one command in the Console (simplest — try this first)**
1. Visit the target site in your browser and **log in** (E-Hentai: https://e-hentai.org; ExHentai: https://exhentai.org; Yandex: https://yandex.com/images)
2. Press **F12** → click the **Console** tab at the top
3. Type `document.cookie` into the input area below and press **Enter**
4. The Console prints the entire Cookie string → **copy it** (something like `ipb_member_id=123; ipb_pass_hash=abc; ...`)
5. Limitation: fields marked **HttpOnly** cannot be retrieved this way — **good enough for E-Hentai**; **some key Yandex fields are HttpOnly, so Method 2 is recommended**

**Method 2: Network panel (complete; recommended for Yandex)**
1. After logging in to the target site, press **F12** → click the **Network** tab
2. **Note: do not type anything into the filter box at the top** (typing filters out requests and empties the list!), leave it blank
3. **Refresh the page** (F5) → a request list appears on the left → **click the first request**
4. On the right, open **Headers** → scroll down to the **Request Headers** section
5. Find the line starting with **`Cookie:`** → **copy the entire line** (everything after `Cookie:`)

The copied content looks like this (actual values vary):
```
yandexuid=1587138991653; ymex=1986384493.yrts.159; Session_id=3:163...:0
```
Paste the entire line into the plugin configuration `default_params.yandex.cookies` / `default_params.ehentai.cookies`.

> **Note:** Yandex has strict anti-scraping; without a Cookie a CAPTCHA may appear and the search returns nothing. Searching ExHentai content through E-Hentai requires a Cookie (containing the three key fields `ipb_member_id`, `ipb_pass_hash`, and `igneous`). Getting it from the domain the plugin actually requests (yandex.com) is the most reliable.

## Changelog

> **[View the changelog →](CHANGELOG.md)**

## Support & Acknowledgements

If you find this plugin helpful, please consider giving it a Star. For issues and suggestions, feel free to open an [Issue](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/issues) or a [Pull Request](https://github.com/OMSociety/astrbot_plugin_reverse_searcher/pulls).

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) open-source chatbot framework
- [astrbot_plugin_img_rev_searcher_Ver2](https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2) the original project

## License & Author

This project is licensed under **AGPL-3.0**.

[@OMSociety](https://github.com/OMSociety)

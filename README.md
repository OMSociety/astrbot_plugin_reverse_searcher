# 适配 AstrBot 的图片反搜聚合插件 Ver2

> ⚡ **核心代码基于**：[kitUIN/PicImageSearch](https://github.com/kitUIN/PicImageSearch)  
> 💡 **架构升级**：本项目已全面转向 **API 优先 (API-First)** 策略，移除笨重的 Selenium/浏览器模拟，通过对接 SerpApi、RapidAPI 等专业服务，提供更加稳健、快速的搜索体验。
  **与原版对比**：
   - 彻底测试并重构了搜图插件：
	 - 移除了没用的bing
	 - 新增了ascii2d, yandex和tracemoe
	 - 彻底解决google和copyseeker不能使用的问题

## 🛠 安装方法

### 方式一：插件市场

- 打开 **AstrBot WebUI** → **插件市场** → 右上角 **Search**
- 搜索与本项目相关的关键词，找到插件后点击安装
- 推荐直接用唯一标识符搜索：  
  ```
  astrbot_plugin_img_rev_searcher_Ver2
  ```

### 方式二：Github 仓库链接

- 打开 **AstrBot WebUI** → **插件管理** → **+ 安装**
- 在出现的输入框内粘贴以下仓库地址并点击安装：
  ```
  https://github.com/Yanlyn/astrbot_plugin_img_rev_searcher_Ver2
  ```

### 📦 依赖库安装

本插件已大幅精简依赖，不再强制要求 Selenium 环境。

在终端执行：

```
pip install -r requirements.txt
```
或手动安装核心库：
```
pip install httpx Pillow pyquery typing_extensions
```

## 🚀 使用说明

| 指令类型 | 格式                | 说明                    |
|:----:|:------------------|:-----------------------|
| 指令头  | `以图搜图`            | 启动图片反搜流程        |
|  参数  | `引擎名`，`图片文件/图片链接` | 两个参数都必填，顺序不限 |

### 指令帮助

#### 方式一：根据提示分步发送
1. 发送 `以图搜图`
2. 发送 `<引擎名>` 和 / 或 `<图片文件/图片链接>`
3. 若有缺漏，补充缺少的参数

#### 方式二：先发送部分参数再补齐
- 发送 `以图搜图 <图片文件/图片链接>`，再发送 `<引擎名>`
- 发送 `以图搜图 <引擎名>`，再发送 `<图片文件/图片链接>`

#### 方式三：一次性发送全部参数
- 发送 `以图搜图 <引擎名> <图片文件/图片链接>`
- 发送 `以图搜图 <图片文件/图片链接> <引擎名>`

#### 方式四：引用历史消息再补齐
- 引用一张图片并发送 `以图搜图 <引擎名>`

### 📝 注意事项
- 图片参数支持 `.gif` 格式，将会截取 **第一帧** 进行搜索
- "引用历史消息再补齐" 不支持文件格式图片

### 支持的搜索引擎

| 引擎        | 网址                                                        | API支持 | 备注 |
|:------------|:------------------------------------------------------------|:--------:|:----|
| **google**  | [SerpApi / Zenserp](https://serpapi.com)                    | ✅ (推荐) | 需API Key，极速、精准，包含AI概览 |
| **copyseeker**| [RapidAPI](https://rapidapi.com/)                         | ✅ (必需) | 需API Key，纯净无广告，效果极佳 |
| **yandex**  | [yandex.com/images](https://yandex.com/images/)             | ❌       | 俄罗斯最强引擎，轻量级爬虫实现 |
| animetrace  | [animetrace.com](https://www.animetrace.com/)               | ✅       | 二次元专用 (无需Key) |
| ascii2d     | [ascii2d.net](https://ascii2d.net/)                         | ❌       | 以色块/特征搜索二次元原图 |
| ehentai     | [e-hentai.org](https://e-hentai.org/)                        | ❌       | 需Cookie (仅ExHentai需要) |
| saucenao    | [saucenao.com](https://saucenao.com/)                        | ✅       | Pixiv插画首选 (免费Key够用) |
| tineye      | [tineye.com](https://tineye.com/)                            | ❌       | 找原图/高清大图专用 |
| tracemoe    | [trace.moe](https://trace.moe/)                              | ✅       | 动画截图找番剧 |
| iqdb        | [iqdb.org](https://iqdb.org/)                                | ❌       | 多站聚合搜索 |
| baidu       | [graph.baidu.com](https://graph.baidu.com/)                  | ❌       | 国内通用搜索 |

*注：Bing 引擎因长期不稳定且无法通过API有效维护，已被移除。*

## ⚠️ 配置文件说明 (API Key 配置)

为了获得最佳体验，强烈建议配置 API Key。这能让你获得"外包"级的稳定服务，无需担心 Cookie 过期或 IP 封禁。

### 1. 配置入口
打开 AstrBot WebUI → `插件管理` → 找到本插件 → `操作` → `插件配置` → **默认参数 (Default Params)**

### 2. Google Lens (推荐)
- **SerpApi Key**: 注册 [SerpApi](https://serpapi.com/) 获取。每月有免费额度，支持高并发，不封号。
- **Zenserp Key**: (备用) 注册 [Zenserp](https://zenserp.com/) 获取。

### 3. Copyseeker (强力推荐)
- **Copyseeker RapidAPI Key**: 在 [RapidAPI](https://rapidapi.com/copyseeker-copyseeker-default/api/reverse-image-search-by-copyseeker) 订阅 Copyseeker API。
- *无需维护任何 Cookie，响应速度仅需几秒。*

### 4. SauceNAO
- **API Key**: 注册 [SauceNAO](https://saucenao.com/user.php) 获取。

### 5. Yandex
- *无需配置*，内置轻量级爬虫。

### 6. E-Hentai / ExHentai
- 仅在使用 ExHentai ("里站") 时需要在 `Default Params -> ehentai -> cookies` 中填写 Cookie。
- 普通 E-Hentai 搜索无需 Cookie。

---

# 🌟 搜索流程及结果示例
<div align="left">

### 第一步：触发搜索流程
<img src="https://github.com/user-attachments/assets/e06a19ab-cd83-4621-95fe-65916a13b37b" alt="1" width="40%"><br><br>

### 第二步：收到图片格式的搜索结果
<img src="https://github.com/user-attachments/assets/56404911-d129-4ebe-ae25-6bddc1e4b26d" alt="2" width="40%"><br><br>

### 第三步：选择是否需要文字格式的搜索结果
<img src="https://github.com/user-attachments/assets/2677d9d0-7908-4b6c-ba3c-cede100b4192" alt="3" width="40%"><br><br>

### 第四步：收到文字格式的搜索结果
<img src="https://github.com/user-attachments/assets/92e3012a-b9c7-4f5b-8e52-80b5791acb66" alt="4" width="40%">

</div>

## 🔄 更新日志 (2025-12-15)

- **[修复] E-Hentai 搜索失效修复**：解决了因上传逻辑缺失文件名导致 E-Hentai 服务器禁用相似度搜索 (No unfiltered results) 的问题。
- **[修复] ExHentai Cookie 注入**：修复了配置文件中 Cookie 无法正确注入到请求中的 bug，现在支持正常使用 ExHentai 搜索。
- **[优化] 错误提示细化**：优化了所有搜索引擎的错误处理逻辑，现在能明确区分“未找到结果”与“网络/API报错”，提供更精准的错误提示。

# 致谢： Gemini & ChatGPT
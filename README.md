# zsxq_downloader

一个 Python 脚本，根据登录账号 Cookie 中的 `access_token`、星球编号和主题创建时间范围，下载知识星球（zsxq）中的主题、评论以及包含的图片与文件链接，并最终合成为 PDF 电子书（内容过多时自动拆分为多个 PDF）。

## 功能特性

- 按时间区间（`EARLY_DATE` ~ `LATE_DATE`）下载指定星球的主题内容。
- 支持只下载精华主题（`ONLY_DIGESTS`）或全部主题。
- 下载主题正文、问答（`question` + `answer`）、发言（`talk`）、任务（`task`）、作业（`solution`）及评论。
- 下载主题、回答、评论中包含的图片（可选，图片会以 base64 内嵌进 PDF）。
- 提取正文中的文件列表信息（文件本身需登录网站下载，脚本仅记录文件名）。
- 生成带标题、作者、创建时间的 HTML，并最终调用 pdfkit 合成 PDF。
- 中断可恢复：下载进度保存到 `temp/crawl_status.json`，已生成内容保存到 `temp/htmls.pkl`，重新运行脚本可从中断点继续。

## 技术栈 / 依赖

本项目为单文件脚本，依赖以下第三方库：

| 依赖 | 用途 |
| --- | --- |
| `requests` | 发起 HTTP 请求（带会话、重试与超时控制） |
| `urllib3` | 请求重试策略（`Retry` / `HTTPAdapter`，随 `requests` 一并安装） |
| `beautifulsoup4` (`bs4`) | 解析与构造 HTML、处理正文中的 @提及 / 话题 / 链接等 |
| `pdfkit` | 将 HTML 转为 PDF |

> `pdfkit` 依赖系统命令 `wkhtmltopdf`，需单独安装并确保其在 `PATH` 中可用。

## 目录结构

```
zsxq_downloader/
├── crawler.py       # 主脚本：抓取 + 生成 PDF
├── pdf_style.css    # PDF 生成时的样式表
├── LICENSE          # MIT 许可证
└── README.md
```

运行时自动生成的目录与文件（无需手动创建）：

- `temp/`：存放抓取状态 `crawl_status.json`、中间 HTML 与 `htmls.pkl`。
- `images/`：下载图片的临时目录（若 `DOWLOAD_PICS=True`，运行结束后视配置自动删除）。

## 安装与环境要求

- Python 3（脚本使用了 `datetime.fromisoformat`，建议 Python 3.7+）。
- 安装 Python 依赖：

```bash
pip install requests beautifulsoup4 pdfkit
```

- 安装 `wkhtmltopdf`（`pdfkit` 的底层依赖）：
  - Windows：从 wkhtmltopdf 官网下载安装包并安装，确保 `wkhtmltopdf` 可执行文件加入 `PATH`。
  - Linux（以 Debian/Ubuntu 为例）：

```bash
sudo apt-get install wkhtmltopdf
```

## 使用方法

1. 编辑 `crawler.py` 开头的配置（至少修改 `ZSXQ_ACCESS_TOKEN` 和 `GROUP_ID`，详见下方「配置说明」）。
2. 运行脚本：

```bash
python crawler.py
```

脚本会按配置抓取主题，在 `temp/` 目录生成中间 HTML，并在当前目录生成 PDF 文件（默认名为「电子书」，内容过多时生成 `电子书0.pdf`、`电子书1.pdf` 等）。

## 配置说明

所有配置项位于 `crawler.py` 顶部，需在运行前按需修改：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `ZSXQ_ACCESS_TOKEN` | `'xxxxxxxxx-...'` | **必填**。登录知识星球后 Cookie 中的 `zsxq_access_token`。 |
| `GROUP_ID` | `'xxxxxxxx'` | **必填**。要下载的星球（小组）编号。 |
| `EARLY_DATE` | `'2024-11-27T00:00:00.000+0800'` | 最早时间。仅当 `FROM_DATE_TO_DATE=True` 时生效，置空表示不限制。 |
| `LATE_DATE` | `'2024-12-25T00:00:00.000+0800'` | 最晚时间。仅当 `FROM_DATE_TO_DATE=True` 时生效，置空表示不限制。 |
| `PDF_FILE_NAME` | `'电子书'` | 生成 PDF 的文件名前缀。 |
| `DOWLOAD_PICS` | `True` | 是否下载图片（`True` / `False`），开启会显著降低速度。 |
| `DOWLOAD_COMMENTS` | `True` | 是否下载评论。 |
| `ONLY_DIGESTS` | `False` | `True` 只下载精华，`False` 下载全部。 |
| `FROM_DATE_TO_DATE` | `True` | 是否按时间区间下载。 |
| `DELETE_PICS_WHEN_DONE` | `True` | 运行结束后是否删除下载的图片。 |
| `DELETE_HTML_WHEN_DONE` | `True` | 运行结束后是否删除生成的 HTML。 |
| `COUNTS_PER_TIME` | `30` | 每次请求加载的主题数，最大可设为 30。 |
| `SLEEP_FLAG` | `True` | 请求之间是否休眠，避免请求过于频繁。 |
| `SLEEP_SEC` | `1` | 休眠秒数，`SLEEP_FLAG=True` 时生效。 |
| `USER_AGENT` | `'Mozilla/5.0 ...'` | 请求使用的 User-Agent。 |
| `TEMP_PATH` | `'temp/'` | 临时文件目录。 |

> 注意：脚本中部分配置项名称存在拼写（`DOWLOAD_PICS`、`DOWLOAD_COMMENTS`），修改时请以源码中的实际变量名为准。

## 输出 / 结果说明

- PDF 文件生成在当前目录，命名为 `{PDF_FILE_NAME}.pdf`；当 HTML 数量超过 2000 时，会按每 2000 个拆分生成 `{PDF_FILE_NAME}0.pdf`、`{PDF_FILE_NAME}1.pdf` 等。
- PDF 页面使用 `pdf_style.css` 样式（Letter 纸张、标题居中红色等）。
- 主题中的文件（附件）不会被下载，仅以「文件列表」形式记录文件名，需登录网站自行下载。

## 注意事项 / 已知限制

- 脚本通过 Cookie `zsxq_access_token` 访问 `https://api.zsxq.com/v2/...` 接口，`access_token` 会过期，失效时需重新登录获取并更新 `ZSXQ_ACCESS_TOKEN`。
- 中断恢复机制：
  - 抓取中断时，进度保存在 `temp/crawl_status.json`（仅在 24 小时内有效）。
  - 抓取完成生成 PDF 前，内容会先存为 `temp/htmls.pkl`。
  - 若 `temp/htmls.pkl` 已存在，再次运行脚本会**直接根据它生成 PDF**，而不会重新抓取；如需重新抓取，需手动删除 `temp/htmls.pkl`。
- `pdfkit` 依赖 `wkhtmltopdf`，未正确安装会导致 PDF 生成失败。
- 抓取文件链接不会下载文件本体。

## 许可证

本项目采用 [MIT License](LICENSE)。

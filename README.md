<div align="center">

# DeckView

**轻量级 Web 文档查看器**

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0.0-orange)](https://github.com/your-repo/deckview)

一个基于 Python 的本地文档服务器，支持在线预览 PPT、PDF、Word 和 Markdown 文件

</div>

---

## 功能特性

| 功能 | 描述 |
|:---:|:---|
| **目录扫描** | 指定目录启动，自动扫描所有文档文件 |
| **目录树导航** | 左侧树形结构展示，支持搜索和折叠 |
| **PPT/Word 预览** | 自动转换为 PDF 并在线预览 |
| **PDF 预览** | 直接预览，支持缩放、翻页 |
| **Markdown 渲染** | 支持 GFM 语法，代码高亮 |
| **实时监听** | 文件变化时自动刷新目录树 |
| **缩略图导航** | PDF/PPT 自动生成页面缩略图 |

## 快速开始

### 环境要求

- **Python** 3.9+
- **LibreOffice**（可选，用于 PPT/Word 转 PDF）

### 安装

```bash
# pip 安装（推荐）
pip install .

# 开发模式安装
pip install -e .
```

### 启动服务

```bash
# 基本用法 - 扫描指定目录
deckview /path/to/your/docs

# 扫描当前目录
deckview .

# 指定端口
deckview /path/to/docs -p 8080

# 允许局域网访问
deckview /path/to/docs --host 0.0.0.0

# 开发模式（代码变化自动重载）
deckview /path/to/docs --reload
```

启动后访问：**http://localhost:8000**

### CLI 参数

```
deckview [目录] [选项]

位置参数:
  directory              要扫描的文档目录（默认为当前目录）

选项:
  -p, --port PORT        服务端口（默认: 8000）
  --host HOST            监听地址（默认: 127.0.0.1）
  --no-watch             禁用文件变化监听
  --reload               开发模式：代码变化时自动重载
  -v, --version          显示版本号
  -h, --help             显示帮助
```

## 安装 LibreOffice

PPT/Word 转换依赖 LibreOffice：

<table>
<tr>
<th>Ubuntu/Debian</th>
<th>macOS</th>
<th>Windows</th>
</tr>
<tr>
<td>

```bash
sudo apt install libreoffice-core
```

</td>
<td>

```bash
brew install libreoffice
```

</td>
<td>

从 [libreoffice.org](https://www.libreoffice.org/) 下载安装

</td>
</tr>
</table>

## 项目结构

```
DeckView/
├── pyproject.toml           # 包配置
└── src/deckview/            # Python 包
    ├── main.py              # FastAPI 入口
    ├── cli.py               # CLI 入口
    ├── api/library.py       # API 路由
    ├── core/config.py       # 配置管理
    ├── services/            # 业务逻辑层
    │   ├── library.py       # 文件扫描服务
    │   ├── watcher.py       # 文件监听服务
    │   ├── conversion.py    # PPT/Word → PDF
    │   └── thumbnail.py     # 缩略图生成
    └── web/                 # 前端资源
        ├── templates/       # HTML 模板
        └── static/          # CSS/JS
```

## API 接口

> API 文档：http://localhost:8000/api/docs

| 接口 | 方法 | 说明 |
|------|:----:|------|
| `/api/library/tree` | GET | 获取目录树 |
| `/api/library/files/{id}` | GET | 获取文件信息 |
| `/api/library/files/{id}/pdf` | GET | 获取 PDF 文件 |
| `/api/library/files/{id}/thumbnails/{page}` | GET | 获取缩略图 |
| `/api/library/files/{id}/content` | GET | 获取 Markdown 内容 |
| `/api/library/events` | GET | SSE 事件流（文件变化通知） |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|:------:|------|
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `8000` | 服务端口 |
| `DECKVIEW_DATA_DIR` | `~/.deckview` | 数据目录（缓存 PDF 和缩略图） |
| `LIBREOFFICE_PATH` | `soffice` | LibreOffice 路径 |
| `CONVERSION_TIMEOUT` | `120` | 转换超时时间（秒） |

## 注意事项

- 默认只监听 `127.0.0.1`，仅本地访问
- 使用 `--host 0.0.0.0` 允许外部访问时请注意安全
- PPT/Word 转换依赖 LibreOffice，首次转换可能较慢
- 转换后的 PDF 和缩略图缓存在 `~/.deckview/` 目录

## 未来计划

<details>
<summary><b>PPT 动画播放支持</b></summary>

当前 PPT 文件通过转换为 PDF 进行预览，无法保留动画和转场效果。未来可能的改进方案：

| 方案 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| **OnlyOffice** | 集成 OnlyOffice Document Server | 开源免费，支持演示模式 | 部署复杂，资源占用大 |
| **Collabora Online** | 基于 LibreOffice 的在线版本 | 开源，支持演示模式 | 复杂动画支持有限 |
| **PPTX → 视频** | 将 PPT 导出为 MP4 视频 | 动画效果完整保留 | 失去交互性 |
| **商业 SDK** | Aspose.Slides 等商业方案 | 高还原度，HTML5 输出 | 需要付费授权 |

如有需要，欢迎提交 Issue 讨论具体需求。

</details>

## 许可证

[MIT License](LICENSE)

---

<div align="center">

**如果这个项目对你有帮助，欢迎 Star 支持！**

</div>

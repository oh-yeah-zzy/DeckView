# DeckView - Web文档查看器

一个基于Python的本地文档服务器，类似mkdocs，支持在线预览PPT、PDF和Markdown文件。

## 功能特性

- **目录扫描**: 指定目录启动，自动扫描所有文档文件
- **目录树导航**: 左侧树形结构展示文件，支持搜索和折叠
- **PPT预览**: PPTX文件自动转换为PDF并在线预览
- **PDF预览**: 直接在线预览PDF文件，支持缩放、翻页
- **Markdown渲染**: 支持GFM语法，代码高亮
- **实时监听**: 文件变化时自动刷新目录树
- **缩略图导航**: PDF/PPT文件自动生成页面缩略图

## 快速开始

### 环境要求

- Python 3.9+
- LibreOffice（可选，用于PPT转PDF）

### 安装

```bash
# 方式一：pip 安装（推荐）
pip install .

# 方式二：开发模式安装
pip install -e .
```

### 启动服务

```bash
# 启动服务，扫描指定目录
deckview /path/to/your/docs

# 扫描当前目录
deckview .

# 指定端口
deckview /path/to/docs -p 8080

# 允许外部访问（局域网）
deckview /path/to/docs --host 0.0.0.0

# 也支持模块方式启动
python -m deckview /path/to/docs
```

启动后访问：http://localhost:8000

### CLI参数

```
用法: deckview [目录] [选项]

位置参数:
  directory             要扫描的文档目录（默认为当前目录）

选项:
  -p, --port PORT       服务端口（默认: 8000）
  --host HOST           监听地址（默认: 127.0.0.1）
  --no-watch            禁用文件变化监听
  --reload              开发模式：代码变化时自动重载
  -v, --version         显示版本号
  -h, --help            显示帮助

示例:
  deckview ~/Documents
  deckview ./docs -p 8080
  deckview . --host 0.0.0.0 --no-watch
```

### 安装LibreOffice（用于PPT转换）

```bash
# Ubuntu/Debian
sudo apt install libreoffice-core

# macOS
brew install libreoffice

# Windows
# 从 https://www.libreoffice.org/ 下载安装
```

## 项目结构

```
DeckView/
├── pyproject.toml        # 包配置
├── src/deckview/         # Python 包
│   ├── api/              # API路由
│   │   └── library.py    # 目录树和文件访问API
│   ├── core/config.py    # 配置管理
│   ├── services/
│   │   ├── library.py    # 文件扫描服务
│   │   ├── watcher.py    # 文件监听服务
│   │   ├── conversion.py # PPT转PDF
│   │   └── thumbnail.py  # 缩略图生成
│   ├── web/              # 前端资源
│   │   ├── templates/    # HTML模板
│   │   └── static/       # CSS/JS
│   ├── cli.py            # CLI入口
│   └── main.py           # FastAPI入口
└── README.md
```

## API接口

| 接口 | 说明 |
|------|------|
| `GET /api/library/tree` | 获取目录树 |
| `GET /api/library/files/{id}` | 获取文件信息 |
| `GET /api/library/files/{id}/pdf` | 获取PDF文件 |
| `GET /api/library/files/{id}/thumbnails/{page}` | 获取缩略图 |
| `GET /api/library/files/{id}/content` | 获取Markdown内容 |
| `GET /api/library/events` | SSE事件流（文件变化通知） |

API文档：http://localhost:8000/api/docs

## 环境变量

支持以下环境变量配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | 127.0.0.1 | 监听地址 |
| `PORT` | 8000 | 服务端口 |
| `DECKVIEW_DATA_DIR` | ~/.deckview | 数据目录（缓存PDF和缩略图） |
| `LIBREOFFICE_PATH` | soffice | LibreOffice路径 |
| `CONVERSION_TIMEOUT` | 120 | 转换超时时间（秒） |

## 注意事项

- 默认只监听 `127.0.0.1`，仅本地访问
- 使用 `--host 0.0.0.0` 允许外部访问时请注意安全
- PPT转换依赖LibreOffice，首次转换可能较慢
- 转换后的PDF和缩略图缓存在 `~/.deckview/` 目录

## 未来计划

### PPT动画播放支持

当前PPT文件通过转换为PDF进行预览，无法保留动画和转场效果。未来可能的改进方案：

| 方案 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| **OnlyOffice** | 集成OnlyOffice Document Server | 开源免费，支持演示模式，还原度较高 | 部署复杂，资源占用大（4GB+内存） |
| **Collabora Online** | 基于LibreOffice的在线版本 | 开源，支持演示模式 | 复杂动画支持有限 |
| **PPTX→视频** | 将PPT导出为MP4视频 | 动画效果完整保留 | 失去交互性，无法逐步点击 |
| **商业SDK** | Aspose.Slides等商业方案 | 高还原度，HTML5输出 | 需要付费授权 |

如有需要，欢迎提交Issue讨论具体需求。

## 许可证

MIT License

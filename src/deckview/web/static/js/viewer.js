/**
 * DeckView 文档查看器JavaScript
 * 处理PDF和Markdown文档的渲染和交互
 */

// 配置PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

// 全局变量
let pdfDoc = null;          // PDF文档对象
let currentPage = 1;        // 当前页码
let totalPages = 0;         // 总页数
let currentScale = 1.0;     // 当前缩放比例
let docInfo = null;         // 文档信息
let rendering = false;      // 是否正在渲染

// DOM元素引用 - 在DOMContentLoaded后初始化
let docTitle, viewerLoading, viewerError, loadingText, errorText;
let pdfViewer, pdfCanvas, markdownViewer, markdownContent;
let pageControls, zoomControls, sidebar, thumbnailList;
let currentPageInput, totalPagesSpan, zoomLevelSpan;
let prevPageBtn, nextPageBtn, zoomInBtn, zoomOutBtn;
let fitPageBtn, fitWidthBtn, fullscreenBtn, sidebarToggle, sidebarExpandBtn;

// 画笔相关DOM引用
let penTools, penToggle, penBrushOptions, penEraserOptions;
let penColor, penSize, eraserSize;
let penEraser, penClear, penUndo, drawingCanvas, drawingCtx;

// 画笔状态
let penEnabled = false;      // 画笔是否启用
let isDrawing = false;       // 是否正在绘制
let isEraser = false;        // 是否橡皮擦模式
let lastX = 0, lastY = 0;    // 上一个绘制点
let drawingHistory = [];     // 绘制历史（用于撤销）
let pageDrawings = {};       // 每页的绘制数据

// ========== Markdown 编辑器状态 ==========
let mdEditor = null;           // CodeMirror 实例
let isEditMode = false;        // 是否编辑模式
let originalContent = '';      // 原始内容（用于检测变化）
let hasUnsavedChanges = false; // 是否有未保存的更改
let previewDebounceTimer = null; // 预览防抖定时器
let autoSaveTimer = null;      // 自动保存定时器

// Markdown 编辑器 DOM 引用
let mdToolbar, mdModeToggle, mdSave, mdStatus;
let mdEditorPane, mdPreviewPane, mdResizer;

/**
 * 初始化DOM引用
 */
function initDOMReferences() {
    docTitle = document.getElementById('docTitle');
    viewerLoading = document.getElementById('viewerLoading');
    viewerError = document.getElementById('viewerError');
    loadingText = document.getElementById('loadingText');
    errorText = document.getElementById('errorText');
    pdfViewer = document.getElementById('pdfViewer');
    pdfCanvas = document.getElementById('pdfCanvas');
    markdownViewer = document.getElementById('markdownViewer');
    markdownContent = document.getElementById('markdownContent');
    pageControls = document.getElementById('pageControls');
    zoomControls = document.getElementById('zoomControls');
    sidebar = document.getElementById('sidebar');
    thumbnailList = document.getElementById('thumbnailList');
    currentPageInput = document.getElementById('currentPage');
    totalPagesSpan = document.getElementById('totalPages');
    zoomLevelSpan = document.getElementById('zoomLevel');

    // 按钮
    prevPageBtn = document.getElementById('prevPage');
    nextPageBtn = document.getElementById('nextPage');
    zoomInBtn = document.getElementById('zoomIn');
    zoomOutBtn = document.getElementById('zoomOut');
    fitPageBtn = document.getElementById('fitPage');
    fitWidthBtn = document.getElementById('fitWidth');
    fullscreenBtn = document.getElementById('fullscreen');
    sidebarToggle = document.getElementById('sidebarToggle');
    sidebarExpandBtn = document.getElementById('sidebarExpandBtn');

    // 画笔相关DOM
    penTools = document.getElementById('penTools');
    penToggle = document.getElementById('penToggle');
    penBrushOptions = document.getElementById('penBrushOptions');
    penEraserOptions = document.getElementById('penEraserOptions');
    penColor = document.getElementById('penColor');
    penSize = document.getElementById('penSize');
    eraserSize = document.getElementById('eraserSize');
    penEraser = document.getElementById('penEraser');
    penClear = document.getElementById('penClear');
    penUndo = document.getElementById('penUndo');
    drawingCanvas = document.getElementById('drawingCanvas');
    if (drawingCanvas) {
        drawingCtx = drawingCanvas.getContext('2d');
    }

    // Markdown 编辑器相关 DOM
    mdToolbar = document.getElementById('mdToolbar');
    mdModeToggle = document.getElementById('mdModeToggle');
    mdSave = document.getElementById('mdSave');
    mdStatus = document.getElementById('mdStatus');
    mdEditorPane = document.getElementById('mdEditorPane');
    mdPreviewPane = document.getElementById('mdPreviewPane');
    mdResizer = document.getElementById('mdResizer');

    console.log('DOM references initialized');
    console.log('fitPageBtn:', fitPageBtn);
    console.log('fitWidthBtn:', fitWidthBtn);
    console.log('drawingCanvas:', drawingCanvas);
}

/**
 * 初始化查看器
 */
async function initViewer() {
    try {
        // 获取文档信息
        const response = await fetch(`/api/library/files/${DOC_ID}`);
        if (!response.ok) {
            throw new Error('文档不存在');
        }

        docInfo = await response.json();
        docTitle.textContent = docInfo.name;

        // 检查文档状态（PPTX可能需要转换）
        if (docInfo.status === 'pending') {
            loadingText.textContent = '首次访问，正在转换文档...';
        }

        // 根据文档类型初始化不同的查看器
        if (docInfo.doc_type === 'markdown') {
            await initMarkdownViewer();
        } else {
            await initPdfViewer();
        }

    } catch (error) {
        console.error('初始化失败:', error);
        showError(error.message);
    }
}

/**
 * 等待文档处理完成
 */
async function waitForProcessing() {
    const maxWait = 120; // 最多等待120秒
    let waited = 0;

    while (waited < maxWait) {
        const response = await fetch(`/api/documents/${DOC_ID}/status`);
        const status = await response.json();

        if (status.status === 'completed') {
            return;
        } else if (status.status === 'failed') {
            throw new Error(status.error_message || '处理失败');
        }

        loadingText.textContent = `文档正在处理中... (${waited}s)`;
        await new Promise(resolve => setTimeout(resolve, 2000));
        waited += 2;
    }

    throw new Error('处理超时');
}

/**
 * 初始化PDF查看器
 */
async function initPdfViewer() {
    loadingText.textContent = '正在加载PDF...';

    try {
        // 加载PDF文档（首次访问PPTX时会自动触发转换）
        const pdfUrl = `/api/library/files/${DOC_ID}/pdf`;
        pdfDoc = await pdfjsLib.getDocument(pdfUrl).promise;
        totalPages = pdfDoc.numPages;

        // 更新UI
        totalPagesSpan.textContent = totalPages;
        currentPageInput.max = totalPages;

        // 显示PDF查看器
        viewerLoading.style.display = 'none';
        pdfViewer.style.display = 'flex';
        pageControls.style.display = 'flex';
        zoomControls.style.display = 'flex';
        if (penTools) penTools.style.display = 'flex';  // 显示画笔工具栏

        // 重新获取文档信息（获取缩略图URL）
        const response = await fetch(`/api/library/files/${DOC_ID}`);
        docInfo = await response.json();

        // 加载缩略图
        loadThumbnails();

        // 先计算合适的缩放比例（适合页面），再渲染第一页，避免闪烁
        await calculateInitialScale();
        await renderPage(1);

    } catch (error) {
        console.error('PDF加载失败:', error);
        throw new Error('PDF加载失败: ' + error.message);
    }
}

/**
 * 计算初始缩放比例 - 默认使用"适合页面"模式
 * 确保整个页面都能在视口内显示
 */
async function calculateInitialScale() {
    if (!pdfDoc) return;

    const page = await pdfDoc.getPage(1);
    const viewport = page.getViewport({ scale: 1 });

    // 获取容器可用尺寸（减去内边距）
    const container = document.querySelector('.viewer-content');
    const containerWidth = container.clientWidth - 40;  // 左右各20px padding
    const containerHeight = container.clientHeight - 40; // 上下各20px padding

    // 计算适合宽度和适合高度的比例
    const scaleWidth = containerWidth / viewport.width;
    const scaleHeight = containerHeight / viewport.height;

    // 取较小值，确保页面完全显示在视口内
    const scale = Math.min(scaleWidth, scaleHeight);

    // 设置缩放比例（不立即渲染，因为renderPage会在之后调用）
    currentScale = Math.max(0.25, Math.min(scale, 4));
    zoomLevelSpan.textContent = Math.round(currentScale * 100) + '%';
}

/**
 * 渲染指定页面
 * @param {number} pageNum - 页码
 */
async function renderPage(pageNum) {
    if (rendering) return;
    rendering = true;

    try {
        // 保存当前页的绘制内容（如果有）
        saveCurrentPageDrawing();

        const page = await pdfDoc.getPage(pageNum);

        // 计算视口
        const viewport = page.getViewport({ scale: currentScale });

        // 设置canvas尺寸
        const canvas = pdfCanvas;
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        // 同步绘图canvas尺寸
        if (drawingCanvas) {
            drawingCanvas.width = viewport.width;
            drawingCanvas.height = viewport.height;
        }

        // 渲染页面
        await page.render({
            canvasContext: context,
            viewport: viewport
        }).promise;

        // 更新当前页
        currentPage = pageNum;
        currentPageInput.value = pageNum;

        // 恢复该页的绘制内容
        restorePageDrawing(pageNum);

        // 清空撤销历史（切换页面时）
        drawingHistory = [];

        // 更新按钮状态
        updatePageButtons();

        // 更新缩略图高亮
        updateThumbnailHighlight();

    } finally {
        rendering = false;
    }
}

/**
 * 加载缩略图
 */
function loadThumbnails() {
    if (!docInfo.thumbnails || docInfo.thumbnails.length === 0) {
        // 没有缩略图，隐藏侧边栏
        sidebar.style.display = 'none';
        return;
    }

    thumbnailList.innerHTML = docInfo.thumbnails.map((thumb, index) => `
        <div class="thumbnail-item ${index === 0 ? 'active' : ''}" data-page="${thumb.page}">
            <img src="${thumb.url}" alt="第${thumb.page}页" loading="lazy">
            <div class="thumbnail-page-num">${thumb.page}</div>
        </div>
    `).join('');

    // 绑定点击事件
    thumbnailList.querySelectorAll('.thumbnail-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = parseInt(item.dataset.page);
            goToPage(page);
        });
    });
}

/**
 * 更新缩略图高亮
 */
function updateThumbnailHighlight() {
    thumbnailList.querySelectorAll('.thumbnail-item').forEach(item => {
        const page = parseInt(item.dataset.page);
        item.classList.toggle('active', page === currentPage);
    });

    // 滚动到当前页的缩略图
    const activeThumb = thumbnailList.querySelector('.thumbnail-item.active');
    if (activeThumb) {
        activeThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

/**
 * 更新页面按钮状态
 */
function updatePageButtons() {
    prevPageBtn.disabled = currentPage <= 1;
    nextPageBtn.disabled = currentPage >= totalPages;
}

/**
 * 跳转到指定页
 * @param {number} pageNum - 页码
 */
function goToPage(pageNum) {
    if (pageNum < 1) pageNum = 1;
    if (pageNum > totalPages) pageNum = totalPages;
    renderPage(pageNum);
}

/**
 * 设置缩放比例
 * @param {number} scale - 缩放比例
 */
function setScale(scale) {
    if (scale < 0.25) scale = 0.25;
    if (scale > 4) scale = 4;
    currentScale = scale;
    zoomLevelSpan.textContent = Math.round(scale * 100) + '%';
    renderPage(currentPage);
}

/**
 * 适合宽度 - 让页面宽度填满容器
 */
async function fitToWidth() {
    if (!pdfDoc) return;

    try {
        const page = await pdfDoc.getPage(currentPage);
        const viewport = page.getViewport({ scale: 1 });
        const container = document.querySelector('.viewer-content');

        // 计算容器可用宽度（减去padding）
        const containerWidth = container.clientWidth - 40;
        const scale = containerWidth / viewport.width;

        console.log('fitToWidth: containerWidth=', containerWidth, 'viewport.width=', viewport.width, 'scale=', scale);

        // 直接设置缩放并渲染
        currentScale = Math.max(0.25, Math.min(scale, 4));
        zoomLevelSpan.textContent = Math.round(currentScale * 100) + '%';
        await renderPageForce(currentPage);
    } catch (error) {
        console.error('fitToWidth error:', error);
    }
}

/**
 * 适合页面 - 让整个页面完全显示在视口内
 */
async function fitToPage() {
    if (!pdfDoc) return;

    try {
        const page = await pdfDoc.getPage(currentPage);
        const viewport = page.getViewport({ scale: 1 });
        const container = document.querySelector('.viewer-content');

        // 计算容器可用尺寸
        const containerWidth = container.clientWidth - 40;
        const containerHeight = container.clientHeight - 40;

        console.log('fitToPage: containerWidth=', containerWidth, 'containerHeight=', containerHeight);
        console.log('fitToPage: viewport.width=', viewport.width, 'viewport.height=', viewport.height);

        // 取宽度和高度缩放的较小值
        const scaleWidth = containerWidth / viewport.width;
        const scaleHeight = containerHeight / viewport.height;
        const scale = Math.min(scaleWidth, scaleHeight);

        console.log('fitToPage: scaleWidth=', scaleWidth, 'scaleHeight=', scaleHeight, 'scale=', scale);

        // 直接设置缩放并渲染
        currentScale = Math.max(0.25, Math.min(scale, 4));
        zoomLevelSpan.textContent = Math.round(currentScale * 100) + '%';
        await renderPageForce(currentPage);
    } catch (error) {
        console.error('fitToPage error:', error);
    }
}

/**
 * 强制渲染页面（忽略rendering标志）
 */
async function renderPageForce(pageNum) {
    // 等待之前的渲染完成
    while (rendering) {
        await new Promise(resolve => setTimeout(resolve, 50));
    }

    rendering = true;

    try {
        // 保存当前页的绘制内容（如果有）
        saveCurrentPageDrawing();

        const page = await pdfDoc.getPage(pageNum);

        // 计算视口
        const viewport = page.getViewport({ scale: currentScale });

        // 设置canvas尺寸
        const canvas = pdfCanvas;
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        // 同步绘图canvas尺寸
        if (drawingCanvas) {
            drawingCanvas.width = viewport.width;
            drawingCanvas.height = viewport.height;
        }

        // 渲染页面
        await page.render({
            canvasContext: context,
            viewport: viewport
        }).promise;

        // 更新当前页
        currentPage = pageNum;
        currentPageInput.value = pageNum;

        // 恢复该页的绘制内容
        restorePageDrawing(pageNum);

        // 更新按钮状态
        updatePageButtons();

        // 更新缩略图高亮
        updateThumbnailHighlight();

    } finally {
        rendering = false;
    }
}

/**
 * 初始化Markdown查看器（增强版 - 支持编辑）
 */
async function initMarkdownViewer() {
    loadingText.textContent = '正在加载Markdown...';

    try {
        // 获取Markdown内容
        const response = await fetch(`/api/library/files/${DOC_ID}/content`);
        if (!response.ok) {
            throw new Error('内容加载失败');
        }

        const content = await response.text();

        // 保存原始内容（用于编辑功能）
        originalContent = content;

        // 配置marked
        marked.setOptions({
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return hljs.highlightAuto(code).value;
            },
            breaks: true,
            gfm: true
        });

        // 渲染Markdown（使用DOMPurify净化HTML防止XSS）
        const html = marked.parse(content);
        const cleanHtml = DOMPurify.sanitize(html, {
            ADD_TAGS: ['iframe'],
            ADD_ATTR: ['target', 'class']
        });

        markdownContent.innerHTML = cleanHtml;

        // 显示Markdown查看器（使用 flex 布局）
        viewerLoading.style.display = 'none';
        markdownViewer.style.display = 'flex';

        // 隐藏PDF相关控件
        sidebar.style.display = 'none';

        // 绑定编辑器事件
        bindMarkdownEditorEvents();

    } catch (error) {
        console.error('Markdown加载失败:', error);
        throw new Error('Markdown加载失败: ' + error.message);
    }
}

// ========== Markdown 编辑功能 ==========

/**
 * 初始化 Markdown 编辑器
 * @param {string} content - Markdown 原始内容
 */
function initMarkdownEditor(content) {
    // 获取 textarea 元素
    const textarea = document.getElementById('mdEditor');
    if (!textarea) {
        console.error('Markdown editor textarea not found');
        return;
    }

    // 初始化 CodeMirror
    mdEditor = CodeMirror.fromTextArea(textarea, {
        mode: 'markdown',
        theme: 'dracula',
        lineNumbers: true,
        lineWrapping: true,
        autofocus: true,  // 自动聚焦
        tabSize: 4,
        indentWithTabs: false,
        inputStyle: 'contenteditable',  // 使用 contenteditable 模式，更好的输入支持
        extraKeys: {
            'Ctrl-S': function(cm) {
                saveMarkdown();
            },
            'Cmd-S': function(cm) {
                saveMarkdown();
            }
        }
    });

    // 设置初始内容
    mdEditor.setValue(content);

    // 监听内容变化
    mdEditor.on('change', handleEditorChange);

    // 延迟刷新以确保正确渲染
    setTimeout(() => {
        mdEditor.refresh();
    }, 50);

    console.log('Markdown editor initialized');
}

/**
 * 处理编辑器内容变化
 */
function handleEditorChange() {
    const currentContent = mdEditor.getValue();

    // 检测是否有未保存的更改
    hasUnsavedChanges = (currentContent !== originalContent);
    updateSaveStatus();

    // 防抖更新预览
    clearTimeout(previewDebounceTimer);
    previewDebounceTimer = setTimeout(() => {
        updateMarkdownPreview(currentContent);
    }, 300);  // 300ms 防抖间隔

    // 设置自动保存（5分钟后自动保存）
    clearTimeout(autoSaveTimer);
    if (hasUnsavedChanges) {
        autoSaveTimer = setTimeout(() => {
            saveMarkdown(true);  // 静默保存
        }, 5 * 60 * 1000);  // 5分钟
    }
}

/**
 * 更新预览内容
 * @param {string} content - Markdown 内容
 */
function updateMarkdownPreview(content) {
    // 使用 marked 解析
    const html = marked.parse(content);

    // 使用 DOMPurify 净化
    const cleanHtml = DOMPurify.sanitize(html, {
        ADD_TAGS: ['iframe'],
        ADD_ATTR: ['target', 'class']
    });

    // 更新预览区域
    markdownContent.innerHTML = cleanHtml;

    // 重新应用代码高亮
    markdownContent.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
}

/**
 * 切换编辑模式
 */
function toggleMarkdownEditMode() {
    isEditMode = !isEditMode;

    if (isEditMode) {
        // 进入编辑模式
        markdownViewer.classList.add('edit-mode');
        mdEditorPane.style.display = 'flex';
        mdResizer.style.display = 'block';
        mdSave.style.display = 'inline-flex';
        mdModeToggle.classList.add('active');
        mdModeToggle.querySelector('.btn-text').textContent = '预览';

        // 初始化编辑器（如果还没有）
        if (!mdEditor) {
            initMarkdownEditor(originalContent);
        }

        // 刷新编辑器以正确渲染（需要等待 DOM 完全更新）
        setTimeout(() => {
            if (mdEditor) {
                mdEditor.refresh();
                mdEditor.focus();
            }
        }, 200);  // 增加延迟确保 DOM 渲染完成

    } else {
        // 退出编辑模式
        if (hasUnsavedChanges) {
            if (!confirm('有未保存的更改，确定要退出编辑模式吗？')) {
                isEditMode = true;  // 恢复状态
                return;
            }
        }

        markdownViewer.classList.remove('edit-mode');
        mdEditorPane.style.display = 'none';
        mdResizer.style.display = 'none';
        mdSave.style.display = 'none';
        mdModeToggle.classList.remove('active');
        mdModeToggle.querySelector('.btn-text').textContent = '编辑';
    }
}

/**
 * 保存 Markdown 内容
 * @param {boolean} silent - 是否静默保存（不显示提示）
 */
async function saveMarkdown(silent = false) {
    if (!mdEditor || !hasUnsavedChanges) {
        return;
    }

    const content = mdEditor.getValue();

    // 更新状态
    updateSaveStatus('saving');

    try {
        const response = await fetch(`/api/library/files/${DOC_ID}/content`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'text/plain; charset=utf-8'
            },
            body: content
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || '保存失败');
        }

        // 更新原始内容
        originalContent = content;
        hasUnsavedChanges = false;

        // 更新状态
        updateSaveStatus('saved');

        if (!silent) {
            // 2秒后清除状态提示
            setTimeout(() => {
                if (!hasUnsavedChanges) {
                    updateSaveStatus();
                }
            }, 2000);
        }

    } catch (error) {
        console.error('保存失败:', error);
        updateSaveStatus('error', error.message);
    }
}

/**
 * 更新保存状态显示
 * @param {string} status - 状态：'unsaved', 'saving', 'saved', 'error'
 * @param {string} message - 错误消息（可选）
 */
function updateSaveStatus(status, message) {
    if (!mdStatus) return;

    // 清除所有状态类
    mdStatus.className = 'md-status';

    switch (status) {
        case 'unsaved':
            mdStatus.textContent = '● 未保存';
            mdStatus.classList.add('unsaved');
            break;
        case 'saving':
            mdStatus.textContent = '保存中...';
            mdStatus.classList.add('saving');
            break;
        case 'saved':
            mdStatus.textContent = '✓ 已保存';
            mdStatus.classList.add('saved');
            break;
        case 'error':
            mdStatus.textContent = '✗ ' + (message || '保存失败');
            mdStatus.classList.add('error');
            break;
        default:
            mdStatus.textContent = '';
    }

    // 如果有未保存的更改，显示未保存状态
    if (!status && hasUnsavedChanges) {
        mdStatus.textContent = '● 未保存';
        mdStatus.classList.add('unsaved');
    }
}

/**
 * 初始化分栏拖动调整
 */
function initMdResizer() {
    if (!mdResizer) return;

    let isResizing = false;
    let startX = 0;
    let startWidthEditor = 0;

    mdResizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidthEditor = mdEditorPane.offsetWidth;
        mdResizer.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const diff = e.clientX - startX;
        const newEditorWidth = startWidthEditor + diff;
        const containerWidth = mdEditorPane.parentElement.offsetWidth;
        const newPreviewWidth = containerWidth - newEditorWidth - 4;  // 4px for resizer

        // 限制最小宽度
        if (newEditorWidth >= 300 && newPreviewWidth >= 300) {
            mdEditorPane.style.flex = 'none';
            mdEditorPane.style.width = newEditorWidth + 'px';

            // 刷新编辑器
            if (mdEditor) {
                mdEditor.refresh();
            }
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            mdResizer.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

/**
 * 绑定 Markdown 编辑器事件
 */
function bindMarkdownEditorEvents() {
    // 模式切换按钮
    if (mdModeToggle) {
        mdModeToggle.addEventListener('click', toggleMarkdownEditMode);
    }

    // 保存按钮
    if (mdSave) {
        mdSave.addEventListener('click', () => saveMarkdown(false));
    }

    // 初始化分栏拖动
    initMdResizer();

    // 页面离开前确认
    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges) {
            e.preventDefault();
            e.returnValue = '有未保存的更改，确定要离开吗？';
            return e.returnValue;
        }
    });

    // 全局快捷键
    document.addEventListener('keydown', (e) => {
        // Ctrl+S / Cmd+S 保存（仅在 Markdown 编辑模式）
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            if (docInfo && docInfo.doc_type === 'markdown' && isEditMode && hasUnsavedChanges) {
                e.preventDefault();
                saveMarkdown(false);
            }
        }
    });

    console.log('Markdown editor events bindind complete');
}

/**
 * 显示错误
 * @param {string} message - 错误信息
 */
function showError(message) {
    viewerLoading.style.display = 'none';
    viewerError.style.display = 'flex';
    errorText.textContent = message;
}

/**
 * 切换全屏
 */
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
        document.body.classList.add('fullscreen');
    } else {
        document.exitFullscreen();
        document.body.classList.remove('fullscreen');
    }
}

/**
 * 切换侧边栏
 */
function toggleSidebar() {
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    if (sidebarToggle) {
        sidebarToggle.textContent = isCollapsed ? '▶' : '◀';
    }
    // 控制展开按钮的显示
    if (sidebarExpandBtn) {
        sidebarExpandBtn.style.display = isCollapsed ? 'flex' : 'none';
    }
}

/**
 * 展开侧边栏
 */
function expandSidebar() {
    sidebar.classList.remove('collapsed');
    if (sidebarToggle) {
        sidebarToggle.textContent = '◀';
    }
    if (sidebarExpandBtn) {
        sidebarExpandBtn.style.display = 'none';
    }
}

// ========== 画笔功能 ==========

/**
 * 保存当前页的绘制内容
 */
function saveCurrentPageDrawing() {
    if (!drawingCanvas || !drawingCtx) return;
    if (currentPage && drawingCanvas.width > 0) {
        pageDrawings[currentPage] = drawingCanvas.toDataURL();
    }
}

/**
 * 恢复指定页的绘制内容
 */
function restorePageDrawing(pageNum) {
    if (!drawingCanvas || !drawingCtx) return;

    // 清空画布
    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);

    // 如果有保存的绘制内容，恢复它
    if (pageDrawings[pageNum]) {
        const img = new Image();
        img.onload = () => {
            drawingCtx.drawImage(img, 0, 0);
        };
        img.src = pageDrawings[pageNum];
    }
}

/**
 * 切换画笔模式
 */
function togglePen() {
    if (isEraser) {
        // 如果当前是橡皮擦模式，直接切换到画笔模式（penEnabled已经是true）
        isEraser = false;
        penEraser.classList.remove('active');
        if (penEraserOptions) penEraserOptions.style.display = 'none';
        drawingCanvas.classList.remove('eraser');
        // 激活画笔选项
        penToggle.classList.add('active');
        if (penBrushOptions) penBrushOptions.style.display = 'flex';
        drawingCanvas.style.cursor = 'crosshair';
        return;  // 直接返回，不执行后续的切换逻辑
    }

    // 正常切换画笔开关
    penEnabled = !penEnabled;

    if (penEnabled) {
        penToggle.classList.add('active');
        if (penBrushOptions) penBrushOptions.style.display = 'flex';
        drawingCanvas.classList.add('active');
        drawingCanvas.style.cursor = 'crosshair';
    } else {
        penToggle.classList.remove('active');
        if (penBrushOptions) penBrushOptions.style.display = 'none';
        drawingCanvas.classList.remove('active');
    }
}

/**
 * 切换橡皮擦模式
 */
function toggleEraser() {
    if (!isEraser) {
        // 启用橡皮擦模式
        if (!penEnabled) {
            // 如果绘图模式未启用，先启用它
            penEnabled = true;
            drawingCanvas.classList.add('active');
        }
        isEraser = true;
        penEraser.classList.add('active');
        if (penEraserOptions) penEraserOptions.style.display = 'flex';
        // 隐藏画笔选项
        penToggle.classList.remove('active');
        if (penBrushOptions) penBrushOptions.style.display = 'none';
        updateEraserCursor();
    } else {
        // 关闭橡皮擦模式，同时关闭绘图模式（什么都不选择）
        isEraser = false;
        penEnabled = false;
        penEraser.classList.remove('active');
        if (penEraserOptions) penEraserOptions.style.display = 'none';
        drawingCanvas.classList.remove('eraser');
        drawingCanvas.classList.remove('active');
    }
}

/**
 * 更新橡皮擦光标大小
 */
function updateEraserCursor() {
    if (!isEraser || !drawingCanvas || !eraserSize) return;

    // 获取橡皮擦大小
    const size = parseInt(eraserSize.value);
    const halfSize = size / 2;

    // 生成SVG光标
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}' viewBox='0 0 ${size} ${size}'><circle cx='${halfSize}' cy='${halfSize}' r='${halfSize - 1}' fill='rgba(255,255,255,0.3)' stroke='white' stroke-width='1'/></svg>`;

    // 编码并设置光标
    const encoded = encodeURIComponent(svg);
    drawingCanvas.style.cursor = `url("data:image/svg+xml,${encoded}") ${halfSize} ${halfSize}, auto`;
}

/**
 * 清除当前页的所有绘制
 */
function clearDrawing() {
    if (!drawingCtx) return;

    // 保存当前状态用于撤销
    saveDrawingState();

    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);

    // 清除保存的绘制数据
    delete pageDrawings[currentPage];
}

/**
 * 保存绘制状态（用于撤销）
 */
function saveDrawingState() {
    if (!drawingCanvas) return;
    drawingHistory.push(drawingCanvas.toDataURL());
    // 限制历史记录数量
    if (drawingHistory.length > 20) {
        drawingHistory.shift();
    }
}

/**
 * 撤销上一步绘制
 */
function undoDrawing() {
    if (drawingHistory.length === 0 || !drawingCtx) return;

    const previousState = drawingHistory.pop();
    const img = new Image();
    img.onload = () => {
        drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        drawingCtx.drawImage(img, 0, 0);
    };
    img.src = previousState;
}

/**
 * 获取鼠标/触摸在canvas上的坐标
 */
function getCanvasCoords(e) {
    const rect = drawingCanvas.getBoundingClientRect();
    const scaleX = drawingCanvas.width / rect.width;
    const scaleY = drawingCanvas.height / rect.height;

    if (e.touches) {
        // 触摸事件
        return {
            x: (e.touches[0].clientX - rect.left) * scaleX,
            y: (e.touches[0].clientY - rect.top) * scaleY
        };
    } else {
        // 鼠标事件
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }
}

/**
 * 开始绘制
 */
function startDrawing(e) {
    if (!penEnabled) return;

    // 保存当前状态用于撤销
    saveDrawingState();

    isDrawing = true;
    const coords = getCanvasCoords(e);
    lastX = coords.x;
    lastY = coords.y;

    // 防止触摸时页面滚动
    e.preventDefault();
}

/**
 * 绘制中
 */
function draw(e) {
    if (!isDrawing || !penEnabled) return;

    const coords = getCanvasCoords(e);

    drawingCtx.beginPath();
    drawingCtx.moveTo(lastX, lastY);
    drawingCtx.lineTo(coords.x, coords.y);

    if (isEraser) {
        // 橡皮擦模式 - 使用独立的橡皮擦大小
        drawingCtx.globalCompositeOperation = 'destination-out';
        drawingCtx.strokeStyle = 'rgba(0,0,0,1)';
        drawingCtx.lineWidth = parseInt(eraserSize.value);
    } else {
        // 画笔模式
        drawingCtx.globalCompositeOperation = 'source-over';
        drawingCtx.strokeStyle = penColor.value;
        drawingCtx.lineWidth = parseInt(penSize.value);
    }

    drawingCtx.lineCap = 'round';
    drawingCtx.lineJoin = 'round';
    drawingCtx.stroke();

    lastX = coords.x;
    lastY = coords.y;

    e.preventDefault();
}

/**
 * 结束绘制
 */
function stopDrawing(e) {
    if (isDrawing) {
        isDrawing = false;
        // 保存当前页的绘制内容
        saveCurrentPageDrawing();
    }
}

/**
 * 绑定画笔事件
 */
function bindPenEvents() {
    if (!drawingCanvas) {
        console.log('Drawing canvas not found, pen features disabled');
        return;
    }

    // 画笔开关
    if (penToggle) {
        penToggle.addEventListener('click', togglePen);
    }

    // 常用颜色按钮
    const colorBtns = document.querySelectorAll('.color-btn');
    colorBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const color = btn.dataset.color;
            // 更新颜色选择器的值
            if (penColor) {
                penColor.value = color;
            }
            // 更新active状态
            colorBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // 如果在橡皮擦模式，切换回画笔模式
            if (isEraser) {
                isEraser = false;
                penEraser.classList.remove('active');
                if (penEraserOptions) penEraserOptions.style.display = 'none';
                drawingCanvas.classList.remove('eraser');
                drawingCanvas.style.cursor = 'crosshair';
            }
        });
    });

    // 自定义颜色选择器变化时，取消预设颜色的选中状态
    if (penColor) {
        penColor.addEventListener('input', () => {
            colorBtns.forEach(b => b.classList.remove('active'));
            // 如果在橡皮擦模式，切换回画笔模式
            if (isEraser) {
                isEraser = false;
                penEraser.classList.remove('active');
                if (penEraserOptions) penEraserOptions.style.display = 'none';
                drawingCanvas.classList.remove('eraser');
                drawingCanvas.style.cursor = 'crosshair';
            }
        });
    }

    // 画笔大小改变时，更新橡皮擦光标
    if (eraserSize) {
        eraserSize.addEventListener('change', () => {
            if (isEraser) {
                updateEraserCursor();
            }
        });
    }

    // 橡皮擦
    if (penEraser) {
        penEraser.addEventListener('click', toggleEraser);
    }

    // 清除
    if (penClear) {
        penClear.addEventListener('click', clearDrawing);
    }

    // 撤销
    if (penUndo) {
        penUndo.addEventListener('click', undoDrawing);
    }

    // 鼠标绘制事件
    drawingCanvas.addEventListener('mousedown', startDrawing);
    drawingCanvas.addEventListener('mousemove', draw);
    drawingCanvas.addEventListener('mouseup', stopDrawing);
    drawingCanvas.addEventListener('mouseout', stopDrawing);

    // 触摸绘制事件（支持触屏设备）
    drawingCanvas.addEventListener('touchstart', startDrawing, { passive: false });
    drawingCanvas.addEventListener('touchmove', draw, { passive: false });
    drawingCanvas.addEventListener('touchend', stopDrawing);
    drawingCanvas.addEventListener('touchcancel', stopDrawing);

    console.log('Pen bindEvents bindind complete');
}

// 事件绑定 - 移到函数中，确保DOM加载完成后执行
function bindEvents() {
    console.log('Binding events...');

    // 检查按钮是否存在
    console.log('fitPageBtn:', fitPageBtn);
    console.log('fitWidthBtn:', fitWidthBtn);

    // 页面导航
    if (prevPageBtn) prevPageBtn.addEventListener('click', () => goToPage(currentPage - 1));
    if (nextPageBtn) nextPageBtn.addEventListener('click', () => goToPage(currentPage + 1));

    if (currentPageInput) {
        currentPageInput.addEventListener('change', (e) => {
            goToPage(parseInt(e.target.value));
        });

        currentPageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                goToPage(parseInt(e.target.value));
            }
        });
    }

    // 缩放控制
    if (zoomInBtn) zoomInBtn.addEventListener('click', () => setScale(currentScale * 1.25));
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => setScale(currentScale / 1.25));
    if (fitPageBtn) {
        fitPageBtn.addEventListener('click', () => {
            console.log('fitPage button clicked');
            fitToPage();
        });
    } else {
        console.error('fitPageBtn not found!');
    }
    if (fitWidthBtn) {
        fitWidthBtn.addEventListener('click', () => {
            console.log('fitWidth button clicked');
            fitToWidth();
        });
    } else {
        console.error('fitWidthBtn not found!');
    }

    // 全屏和侧边栏
    if (fullscreenBtn) fullscreenBtn.addEventListener('click', toggleFullscreen);
    if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);
    if (sidebarExpandBtn) sidebarExpandBtn.addEventListener('click', expandSidebar);

    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
        // 如果在输入框中，不处理快捷键
        if (e.target.tagName === 'INPUT') return;

        switch (e.key) {
            case 'ArrowLeft':
            case 'PageUp':
                e.preventDefault();
                goToPage(currentPage - 1);
                break;
            case 'ArrowRight':
            case 'PageDown':
            case ' ':
                e.preventDefault();
                goToPage(currentPage + 1);
                break;
            case 'Home':
                e.preventDefault();
                goToPage(1);
                break;
            case 'End':
                e.preventDefault();
                goToPage(totalPages);
                break;
            case '+':
            case '=':
                e.preventDefault();
                setScale(currentScale * 1.25);
                break;
            case '-':
                e.preventDefault();
                setScale(currentScale / 1.25);
                break;
            case 'f':
            case 'F':
                e.preventDefault();
                toggleFullscreen();
                break;
        }
    });

    // 窗口大小变化时重新适配
    window.addEventListener('resize', () => {
        if (pdfDoc) {
            // 延迟执行避免频繁渲染
            clearTimeout(window.resizeTimer);
            window.resizeTimer = setTimeout(() => {
                console.log('Window resized, calling fitToPage');
                // 重新适配到页面，保持最佳显示效果
                fitToPage();
            }, 200);
        }
    });

    console.log('Events bindind complete');
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded');
    initDOMReferences();  // 先初始化DOM引用
    bindEvents();         // 然后绑定事件
    bindPenEvents();      // 绑定画笔事件
    initViewer();         // 最后初始化查看器
});

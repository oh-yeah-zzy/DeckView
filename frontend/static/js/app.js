/**
 * DeckView 主应用JavaScript - v3.0 目录树 + 预览模式
 * 处理目录树展示、文件导航、预览和实时更新
 */

// 配置PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

// API基础路径
const API_BASE = '/api/library';

// DOM元素引用 - 侧边栏
const fileTree = document.getElementById('fileTree');
const searchInput = document.getElementById('searchInput');
const refreshBtn = document.getElementById('refreshBtn');
const expandAllBtn = document.getElementById('expandAllBtn');
const collapseAllBtn = document.getElementById('collapseAllBtn');
const sidebarFooter = document.getElementById('sidebarFooter');
const connectionStatus = document.getElementById('connectionStatus');
const toast = document.getElementById('toast');

// DOM元素引用 - 预览面板
const welcomePage = document.getElementById('welcomePage');
const previewPanel = document.getElementById('previewPanel');
const previewTitle = document.getElementById('previewTitle');
const previewContent = document.getElementById('previewContent');
const previewLoading = document.getElementById('previewLoading');
const previewLoadingText = document.getElementById('previewLoadingText');
const previewError = document.getElementById('previewError');
const previewErrorText = document.getElementById('previewErrorText');
const openInNewPageBtn = document.getElementById('openInNewPage');

// PDF 相关 DOM
const previewPdfViewer = document.getElementById('previewPdfViewer');
const previewPdfCanvas = document.getElementById('previewPdfCanvas');
const previewDrawingCanvas = document.getElementById('previewDrawingCanvas');
const previewPageControls = document.getElementById('previewPageControls');
const previewCurrentPage = document.getElementById('previewCurrentPage');
const previewTotalPages = document.getElementById('previewTotalPages');
const previewPrevPage = document.getElementById('previewPrevPage');
const previewNextPage = document.getElementById('previewNextPage');
const previewZoomControls = document.getElementById('previewZoomControls');
const previewZoomLevel = document.getElementById('previewZoomLevel');
const previewZoomIn = document.getElementById('previewZoomIn');
const previewZoomOut = document.getElementById('previewZoomOut');
const previewFitPage = document.getElementById('previewFitPage');

// 画笔相关 DOM
const previewPenTools = document.getElementById('previewPenTools');
const previewPenToggle = document.getElementById('previewPenToggle');
const previewPenBrushOptions = document.getElementById('previewPenBrushOptions');
const previewPenColor = document.getElementById('previewPenColor');
const previewPenSize = document.getElementById('previewPenSize');
const previewPenEraser = document.getElementById('previewPenEraser');
const previewPenEraserOptions = document.getElementById('previewPenEraserOptions');
const previewEraserSize = document.getElementById('previewEraserSize');
const previewPenClear = document.getElementById('previewPenClear');
const previewPenUndo = document.getElementById('previewPenUndo');

// Markdown 相关 DOM
const previewMarkdownViewer = document.getElementById('previewMarkdownViewer');
const previewMarkdownContent = document.getElementById('previewMarkdownContent');
const previewMdEdit = document.getElementById('previewMdEdit');
const previewMdSave = document.getElementById('previewMdSave');
const previewMdStatus = document.getElementById('previewMdStatus');
const previewMdEditorPane = document.getElementById('previewMdEditorPane');
const previewMdResizer = document.getElementById('previewMdResizer');
const previewMdPreviewPane = document.getElementById('previewMdPreviewPane');

// 目录树状态
let treeData = null;
let fileCount = 0;
let eventSource = null;

// 当前预览状态
let currentFileId = null;
let currentDocType = null;
let currentFileName = null;

// PDF 预览状态
let pdfDoc = null;
let currentPage = 1;
let totalPages = 0;
let currentScale = 1.0;
let rendering = false;

// 画笔状态
let penEnabled = false;
let isDrawing = false;
let isEraser = false;
let lastX = 0, lastY = 0;
let drawingHistory = [];
let pageDrawings = {};
let drawingCtx = null;

// Markdown 编辑状态
let mdEditor = null;
let isEditMode = false;
let originalContent = '';
let hasUnsavedChanges = false;
let previewDebounceTimer = null;
let autoSaveTimer = null;

// ============ 工具函数 ============

function showToast(message, type = 'info') {
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileIcon(docType) {
    const icons = { 'pptx': '📊', 'pdf': '📄', 'markdown': '📝', 'docx': '📃' };
    return icons[docType] || '📁';
}

function getTypeBadge(docType) {
    const labels = { 'pptx': 'PPT', 'pdf': 'PDF', 'markdown': 'MD', 'docx': 'WORD' };
    return labels[docType] || '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============ 目录树功能 ============

async function loadTree(refresh = false) {
    try {
        fileTree.innerHTML = '<div class="loading">加载中...</div>';
        const url = refresh ? `${API_BASE}/tree?refresh=true` : `${API_BASE}/tree`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('加载失败');

        treeData = await response.json();
        fileCount = 0;
        renderTree(treeData);
        sidebarFooter.innerHTML = `<span class="file-count">共 ${fileCount} 个文件</span>`;
        restoreExpandState();
    } catch (error) {
        console.error('加载目录树失败:', error);
        fileTree.innerHTML = `
            <div class="loading">
                加载失败，请检查服务是否正常运行
                <br><br>
                <button class="btn-icon" onclick="loadTree(true)">🔄 重试</button>
            </div>
        `;
    }
}

function renderTree(node, level = 0) {
    if (level === 0) fileTree.innerHTML = '';
    if (!node.children || node.children.length === 0) {
        if (level === 0) {
            fileTree.innerHTML = '<div class="loading">该目录下没有支持的文档文件</div>';
        }
        return;
    }

    const container = level === 0 ? fileTree : document.createElement('div');
    if (level > 0) {
        container.className = 'tree-children';
        container.dataset.path = node.path;
    }

    for (const child of node.children) {
        const nodeEl = createTreeNode(child, level);
        container.appendChild(nodeEl);
    }
    return container;
}

function createTreeNode(node, level) {
    const wrapper = document.createElement('div');
    wrapper.className = 'tree-node';

    const item = document.createElement('div');
    item.className = 'tree-item';
    item.dataset.level = level;
    item.dataset.path = node.path;

    if (node.type === 'dir') {
        item.innerHTML = `
            <span class="tree-toggle">▶</span>
            <span class="tree-icon">📁</span>
            <span class="tree-name">${escapeHtml(node.name)}</span>
        `;
        item.addEventListener('click', (e) => {
            toggleDirectory(item, wrapper);
            e.stopPropagation();
        });
        wrapper.appendChild(item);

        if (node.children && node.children.length > 0) {
            const childContainer = document.createElement('div');
            childContainer.className = 'tree-children';
            childContainer.dataset.path = node.path;
            for (const child of node.children) {
                const childNode = createTreeNode(child, level + 1);
                childContainer.appendChild(childNode);
            }
            wrapper.appendChild(childContainer);
        }
    } else {
        fileCount++;
        const icon = getFileIcon(node.doc_type);
        const badge = getTypeBadge(node.doc_type);
        const sizeStr = formatSize(node.size);

        item.innerHTML = `
            <span class="tree-toggle placeholder"></span>
            <span class="tree-icon">${icon}</span>
            <span class="tree-name" title="${escapeHtml(node.path)} (${sizeStr})">${escapeHtml(node.name)}</span>
            <span class="tree-badge ${node.doc_type}">${badge}</span>
        `;
        item.dataset.fileId = node.id;
        item.dataset.docType = node.doc_type;

        item.addEventListener('click', () => {
            openFile(node.id, node.name, node.doc_type);
        });
        wrapper.appendChild(item);
    }
    return wrapper;
}

function toggleDirectory(item, wrapper) {
    const toggle = item.querySelector('.tree-toggle');
    const children = wrapper.querySelector('.tree-children');
    if (!children) return;

    const isExpanded = toggle.classList.contains('expanded');
    if (isExpanded) {
        toggle.classList.remove('expanded');
        children.classList.remove('expanded');
        item.querySelector('.tree-icon').textContent = '📁';
    } else {
        toggle.classList.add('expanded');
        children.classList.add('expanded');
        item.querySelector('.tree-icon').textContent = '📂';
    }
    saveExpandState();
}

function expandAll() {
    document.querySelectorAll('.tree-toggle:not(.placeholder)').forEach(t => t.classList.add('expanded'));
    document.querySelectorAll('.tree-children').forEach(c => c.classList.add('expanded'));
    document.querySelectorAll('.tree-item .tree-icon').forEach(i => { if (i.textContent === '📁') i.textContent = '📂'; });
    saveExpandState();
}

function collapseAll() {
    document.querySelectorAll('.tree-toggle').forEach(t => t.classList.remove('expanded'));
    document.querySelectorAll('.tree-children').forEach(c => c.classList.remove('expanded'));
    document.querySelectorAll('.tree-item .tree-icon').forEach(i => { if (i.textContent === '📂') i.textContent = '📁'; });
    saveExpandState();
}

function saveExpandState() {
    const expanded = [];
    document.querySelectorAll('.tree-toggle.expanded').forEach(toggle => {
        const item = toggle.closest('.tree-item');
        if (item && item.dataset.path) expanded.push(item.dataset.path);
    });
    localStorage.setItem('deckview_expanded', JSON.stringify(expanded));
}

function restoreExpandState() {
    try {
        const expanded = JSON.parse(localStorage.getItem('deckview_expanded') || '[]');
        expanded.forEach(path => {
            const item = document.querySelector(`.tree-item[data-path="${path}"]`);
            if (item) {
                const wrapper = item.closest('.tree-node');
                if (wrapper) {
                    const toggle = item.querySelector('.tree-toggle');
                    const children = wrapper.querySelector('.tree-children');
                    if (toggle && children) {
                        toggle.classList.add('expanded');
                        children.classList.add('expanded');
                        item.querySelector('.tree-icon').textContent = '📂';
                    }
                }
            }
        });
    } catch (e) { console.error('恢复展开状态失败:', e); }
}

function filterTree(keyword) {
    keyword = keyword.toLowerCase().trim();
    document.querySelectorAll('.tree-item').forEach(item => {
        const name = item.querySelector('.tree-name').textContent.toLowerCase();
        const path = (item.dataset.path || '').toLowerCase();

        if (!keyword || name.includes(keyword) || path.includes(keyword)) {
            item.classList.remove('hidden');
            let parent = item.closest('.tree-children');
            while (parent) {
                parent.classList.add('expanded');
                const parentItem = parent.previousElementSibling;
                if (parentItem) {
                    const toggle = parentItem.querySelector('.tree-toggle');
                    if (toggle) toggle.classList.add('expanded');
                    const icon = parentItem.querySelector('.tree-icon');
                    if (icon && icon.textContent === '📁') icon.textContent = '📂';
                }
                parent = parent.parentElement.closest('.tree-children');
            }
        } else {
            item.classList.add('hidden');
        }
    });
}

// ============ 预览功能 ============

async function openFile(fileId, fileName, docType) {
    // 设置当前激活项
    document.querySelectorAll('.tree-item.active').forEach(el => el.classList.remove('active'));
    const item = document.querySelector(`.tree-item[data-file-id="${fileId}"]`);
    if (item) item.classList.add('active');

    // 保存当前文件信息
    currentFileId = fileId;
    currentFileName = fileName;
    currentDocType = docType;

    // 显示预览面板
    welcomePage.style.display = 'none';
    previewPanel.style.display = 'flex';
    previewTitle.textContent = fileName;

    // 重置预览区域
    resetPreview();

    // 显示加载状态
    previewLoading.style.display = 'flex';
    previewLoadingText.textContent = '正在加载...';

    try {
        if (docType === 'markdown') {
            await loadMarkdownPreview(fileId);
        } else {
            await loadPdfPreview(fileId);
        }
    } catch (error) {
        console.error('加载预览失败:', error);
        showPreviewError(error.message);
    }
}

function resetPreview() {
    // 隐藏所有内容区域
    previewPdfViewer.style.display = 'none';
    previewMarkdownViewer.style.display = 'none';
    previewLoading.style.display = 'none';
    previewError.style.display = 'none';

    // 隐藏工具栏控件
    previewPageControls.style.display = 'none';
    previewZoomControls.style.display = 'none';
    previewPenTools.style.display = 'none';
    previewMdEdit.style.display = 'none';
    previewMdSave.style.display = 'none';
    previewMdStatus.textContent = '';

    // 重置 Markdown 编辑状态
    if (mdEditor) {
        mdEditor.toTextArea();
        mdEditor = null;
    }
    isEditMode = false;
    hasUnsavedChanges = false;
    previewMarkdownViewer.classList.remove('edit-mode');
    previewMdEditorPane.style.display = 'none';
    previewMdResizer.style.display = 'none';

    // 重置 PDF 状态
    pdfDoc = null;
    currentPage = 1;
    totalPages = 0;
    currentScale = 1.0;

    // 重置画笔状态
    penEnabled = false;
    isEraser = false;
    drawingHistory = [];
    pageDrawings = {};
    previewPenToggle.classList.remove('active');
    previewPenEraser.classList.remove('active');
    previewPenBrushOptions.style.display = 'none';
    previewPenEraserOptions.style.display = 'none';
    if (previewDrawingCanvas) {
        previewDrawingCanvas.classList.remove('active');
    }
}

function showPreviewError(message) {
    previewLoading.style.display = 'none';
    previewError.style.display = 'flex';
    previewErrorText.textContent = message || '加载失败';
}

// ============ PDF 预览功能 ============

async function loadPdfPreview(fileId) {
    previewLoadingText.textContent = '正在加载 PDF...';

    const pdfUrl = `${API_BASE}/files/${fileId}/pdf`;
    pdfDoc = await pdfjsLib.getDocument(pdfUrl).promise;
    totalPages = pdfDoc.numPages;

    // 更新 UI
    previewTotalPages.textContent = totalPages;
    previewCurrentPage.max = totalPages;
    previewCurrentPage.value = 1;

    // 显示 PDF 查看器
    previewLoading.style.display = 'none';
    previewPdfViewer.style.display = 'flex';
    previewPageControls.style.display = 'flex';
    previewZoomControls.style.display = 'flex';
    previewPenTools.style.display = 'flex';

    // 初始化绘图画布
    if (previewDrawingCanvas) {
        drawingCtx = previewDrawingCanvas.getContext('2d');
    }

    // 计算初始缩放并渲染
    await calculateInitialScale();
    await renderPdfPage(1);
}

async function calculateInitialScale() {
    if (!pdfDoc) return;
    const page = await pdfDoc.getPage(1);
    const viewport = page.getViewport({ scale: 1 });

    const containerWidth = previewContent.clientWidth - 40;
    const containerHeight = previewContent.clientHeight - 40;

    const scaleWidth = containerWidth / viewport.width;
    const scaleHeight = containerHeight / viewport.height;
    const scale = Math.min(scaleWidth, scaleHeight);

    currentScale = Math.max(0.25, Math.min(scale, 4));
    previewZoomLevel.textContent = Math.round(currentScale * 100) + '%';
}

async function renderPdfPage(pageNum) {
    if (rendering || !pdfDoc) return;
    rendering = true;

    try {
        saveCurrentPageDrawing();

        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: currentScale });

        const canvas = previewPdfCanvas;
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        if (previewDrawingCanvas) {
            previewDrawingCanvas.width = viewport.width;
            previewDrawingCanvas.height = viewport.height;
        }

        await page.render({ canvasContext: context, viewport: viewport }).promise;

        currentPage = pageNum;
        previewCurrentPage.value = pageNum;

        restorePageDrawing(pageNum);
        drawingHistory = [];
        updatePageButtons();
    } finally {
        rendering = false;
    }
}

function updatePageButtons() {
    previewPrevPage.disabled = currentPage <= 1;
    previewNextPage.disabled = currentPage >= totalPages;
}

function goToPage(pageNum) {
    if (pageNum < 1) pageNum = 1;
    if (pageNum > totalPages) pageNum = totalPages;
    renderPdfPage(pageNum);
}

function setScale(scale) {
    if (scale < 0.25) scale = 0.25;
    if (scale > 4) scale = 4;
    currentScale = scale;
    previewZoomLevel.textContent = Math.round(scale * 100) + '%';
    renderPdfPage(currentPage);
}

async function fitToPage() {
    if (!pdfDoc) return;
    const page = await pdfDoc.getPage(currentPage);
    const viewport = page.getViewport({ scale: 1 });

    const containerWidth = previewContent.clientWidth - 40;
    const containerHeight = previewContent.clientHeight - 40;

    const scaleWidth = containerWidth / viewport.width;
    const scaleHeight = containerHeight / viewport.height;
    const scale = Math.min(scaleWidth, scaleHeight);

    currentScale = Math.max(0.25, Math.min(scale, 4));
    previewZoomLevel.textContent = Math.round(currentScale * 100) + '%';
    renderPdfPage(currentPage);
}

// ============ 画笔功能 ============

function togglePen() {
    if (isEraser) {
        isEraser = false;
        previewPenEraser.classList.remove('active');
        previewPenEraserOptions.style.display = 'none';
        previewDrawingCanvas.classList.remove('eraser');
        previewPenToggle.classList.add('active');
        previewPenBrushOptions.style.display = 'flex';
        previewDrawingCanvas.style.cursor = 'crosshair';
        return;
    }

    penEnabled = !penEnabled;
    if (penEnabled) {
        previewPenToggle.classList.add('active');
        previewPenBrushOptions.style.display = 'flex';
        previewDrawingCanvas.classList.add('active');
        previewDrawingCanvas.style.cursor = 'crosshair';
    } else {
        previewPenToggle.classList.remove('active');
        previewPenBrushOptions.style.display = 'none';
        previewDrawingCanvas.classList.remove('active');
    }
}

function toggleEraser() {
    if (!isEraser) {
        if (!penEnabled) {
            penEnabled = true;
            previewDrawingCanvas.classList.add('active');
        }
        isEraser = true;
        previewPenEraser.classList.add('active');
        previewPenEraserOptions.style.display = 'flex';
        previewPenToggle.classList.remove('active');
        previewPenBrushOptions.style.display = 'none';
        updateEraserCursor();
    } else {
        isEraser = false;
        penEnabled = false;
        previewPenEraser.classList.remove('active');
        previewPenEraserOptions.style.display = 'none';
        previewDrawingCanvas.classList.remove('eraser');
        previewDrawingCanvas.classList.remove('active');
    }
}

function updateEraserCursor() {
    if (!isEraser || !previewDrawingCanvas || !previewEraserSize) return;
    const size = parseInt(previewEraserSize.value);
    const halfSize = size / 2;
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}' viewBox='0 0 ${size} ${size}'><circle cx='${halfSize}' cy='${halfSize}' r='${halfSize - 1}' fill='rgba(255,255,255,0.3)' stroke='white' stroke-width='1'/></svg>`;
    const encoded = encodeURIComponent(svg);
    previewDrawingCanvas.style.cursor = `url("data:image/svg+xml,${encoded}") ${halfSize} ${halfSize}, auto`;
}

function saveCurrentPageDrawing() {
    if (!previewDrawingCanvas || !drawingCtx) return;
    if (currentPage && previewDrawingCanvas.width > 0) {
        pageDrawings[currentPage] = previewDrawingCanvas.toDataURL();
    }
}

function restorePageDrawing(pageNum) {
    if (!previewDrawingCanvas || !drawingCtx) return;
    drawingCtx.clearRect(0, 0, previewDrawingCanvas.width, previewDrawingCanvas.height);
    if (pageDrawings[pageNum]) {
        const img = new Image();
        img.onload = () => { drawingCtx.drawImage(img, 0, 0); };
        img.src = pageDrawings[pageNum];
    }
}

function saveDrawingState() {
    if (!previewDrawingCanvas) return;
    drawingHistory.push(previewDrawingCanvas.toDataURL());
    if (drawingHistory.length > 20) drawingHistory.shift();
}

function clearDrawing() {
    if (!drawingCtx) return;
    saveDrawingState();
    drawingCtx.clearRect(0, 0, previewDrawingCanvas.width, previewDrawingCanvas.height);
    delete pageDrawings[currentPage];
}

function undoDrawing() {
    if (drawingHistory.length === 0 || !drawingCtx) return;
    const previousState = drawingHistory.pop();
    const img = new Image();
    img.onload = () => {
        drawingCtx.clearRect(0, 0, previewDrawingCanvas.width, previewDrawingCanvas.height);
        drawingCtx.drawImage(img, 0, 0);
    };
    img.src = previousState;
}

function getCanvasCoords(e) {
    const rect = previewDrawingCanvas.getBoundingClientRect();
    const scaleX = previewDrawingCanvas.width / rect.width;
    const scaleY = previewDrawingCanvas.height / rect.height;
    if (e.touches) {
        return { x: (e.touches[0].clientX - rect.left) * scaleX, y: (e.touches[0].clientY - rect.top) * scaleY };
    }
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
}

function startDrawing(e) {
    if (!penEnabled) return;
    saveDrawingState();
    isDrawing = true;
    const coords = getCanvasCoords(e);
    lastX = coords.x;
    lastY = coords.y;
    e.preventDefault();
}

function draw(e) {
    if (!isDrawing || !penEnabled) return;
    const coords = getCanvasCoords(e);

    drawingCtx.beginPath();
    drawingCtx.moveTo(lastX, lastY);
    drawingCtx.lineTo(coords.x, coords.y);

    if (isEraser) {
        drawingCtx.globalCompositeOperation = 'destination-out';
        drawingCtx.strokeStyle = 'rgba(0,0,0,1)';
        drawingCtx.lineWidth = parseInt(previewEraserSize.value);
    } else {
        drawingCtx.globalCompositeOperation = 'source-over';
        drawingCtx.strokeStyle = previewPenColor.value;
        drawingCtx.lineWidth = parseInt(previewPenSize.value);
    }

    drawingCtx.lineCap = 'round';
    drawingCtx.lineJoin = 'round';
    drawingCtx.stroke();

    lastX = coords.x;
    lastY = coords.y;
    e.preventDefault();
}

function stopDrawing() {
    if (isDrawing) {
        isDrawing = false;
        saveCurrentPageDrawing();
    }
}

// ============ Markdown 预览功能 ============

async function loadMarkdownPreview(fileId) {
    previewLoadingText.textContent = '正在加载 Markdown...';

    const response = await fetch(`${API_BASE}/files/${fileId}/content`);
    if (!response.ok) throw new Error('加载失败');

    const content = await response.text();
    originalContent = content;

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

    const html = marked.parse(content);
    const cleanHtml = DOMPurify.sanitize(html, {
        ADD_TAGS: ['iframe'],
        ADD_ATTR: ['target', 'class']
    });

    previewMarkdownContent.innerHTML = cleanHtml;

    previewLoading.style.display = 'none';
    previewMarkdownViewer.style.display = 'flex';
    previewMdEdit.style.display = 'inline-flex';
}

function toggleMdEditMode() {
    isEditMode = !isEditMode;

    if (isEditMode) {
        previewMarkdownViewer.classList.add('edit-mode');
        previewMdEditorPane.style.display = 'flex';
        previewMdResizer.style.display = 'block';
        previewMdSave.style.display = 'inline-flex';
        previewMdEdit.querySelector('.btn-text').textContent = '预览';
        previewMdEdit.classList.add('active');

        if (!mdEditor) {
            initMdEditor(originalContent);
        }

        setTimeout(() => {
            if (mdEditor) {
                mdEditor.refresh();
                mdEditor.focus();
            }
        }, 200);
    } else {
        if (hasUnsavedChanges) {
            if (!confirm('有未保存的更改，确定要退出编辑模式吗？')) {
                isEditMode = true;
                return;
            }
        }

        previewMarkdownViewer.classList.remove('edit-mode');
        previewMdEditorPane.style.display = 'none';
        previewMdResizer.style.display = 'none';
        previewMdSave.style.display = 'none';
        previewMdEdit.querySelector('.btn-text').textContent = '编辑';
        previewMdEdit.classList.remove('active');
    }
}

function initMdEditor(content) {
    const textarea = document.getElementById('previewMdEditor');
    if (!textarea) return;

    mdEditor = CodeMirror.fromTextArea(textarea, {
        mode: 'markdown',
        theme: 'dracula',
        lineNumbers: true,
        lineWrapping: true,
        autofocus: true,
        tabSize: 4,
        indentWithTabs: false,
        inputStyle: 'contenteditable',
        extraKeys: {
            'Ctrl-S': () => saveMdContent(),
            'Cmd-S': () => saveMdContent()
        }
    });

    mdEditor.setValue(content);
    mdEditor.on('change', handleMdEditorChange);

    setTimeout(() => { mdEditor.refresh(); }, 50);
}

function handleMdEditorChange() {
    const currentContent = mdEditor.getValue();
    hasUnsavedChanges = (currentContent !== originalContent);
    updateMdSaveStatus();

    clearTimeout(previewDebounceTimer);
    previewDebounceTimer = setTimeout(() => {
        updateMdPreview(currentContent);
    }, 300);

    clearTimeout(autoSaveTimer);
    if (hasUnsavedChanges) {
        autoSaveTimer = setTimeout(() => { saveMdContent(true); }, 5 * 60 * 1000);
    }
}

function updateMdPreview(content) {
    const html = marked.parse(content);
    const cleanHtml = DOMPurify.sanitize(html, {
        ADD_TAGS: ['iframe'],
        ADD_ATTR: ['target', 'class']
    });
    previewMarkdownContent.innerHTML = cleanHtml;
    previewMarkdownContent.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
}

async function saveMdContent(silent = false) {
    if (!mdEditor || !hasUnsavedChanges) return;

    const content = mdEditor.getValue();
    updateMdSaveStatus('saving');

    try {
        const response = await fetch(`${API_BASE}/files/${currentFileId}/content`, {
            method: 'PUT',
            headers: { 'Content-Type': 'text/plain; charset=utf-8' },
            body: content
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || '保存失败');
        }

        originalContent = content;
        hasUnsavedChanges = false;
        updateMdSaveStatus('saved');

        if (!silent) {
            setTimeout(() => { if (!hasUnsavedChanges) updateMdSaveStatus(); }, 2000);
        }
    } catch (error) {
        console.error('保存失败:', error);
        updateMdSaveStatus('error', error.message);
    }
}

function updateMdSaveStatus(status, message) {
    if (!previewMdStatus) return;
    previewMdStatus.className = 'md-status';

    switch (status) {
        case 'unsaved': previewMdStatus.textContent = '● 未保存'; previewMdStatus.classList.add('unsaved'); break;
        case 'saving': previewMdStatus.textContent = '保存中...'; previewMdStatus.classList.add('saving'); break;
        case 'saved': previewMdStatus.textContent = '✓ 已保存'; previewMdStatus.classList.add('saved'); break;
        case 'error': previewMdStatus.textContent = '✗ ' + (message || '保存失败'); previewMdStatus.classList.add('error'); break;
        default: previewMdStatus.textContent = '';
    }

    if (!status && hasUnsavedChanges) {
        previewMdStatus.textContent = '● 未保存';
        previewMdStatus.classList.add('unsaved');
    }
}

// ============ SSE 连接 ============

function connectEventSource() {
    if (eventSource) eventSource.close();

    eventSource = new EventSource(`${API_BASE}/events`);

    eventSource.onopen = () => {
        connectionStatus.className = 'connection-status connected';
        connectionStatus.querySelector('.status-text').textContent = '已连接';
    };

    eventSource.onmessage = (event) => {
        if (event.data === 'tree_changed') {
            showToast('文件变化，正在刷新...', 'info');
            loadTree(true);
        }
    };

    eventSource.onerror = () => {
        connectionStatus.className = 'connection-status disconnected';
        connectionStatus.querySelector('.status-text').textContent = '已断开';
        setTimeout(() => {
            if (eventSource.readyState === EventSource.CLOSED) connectEventSource();
        }, 5000);
    };
}

// ============ 事件绑定 ============

function bindEvents() {
    // 侧边栏事件
    refreshBtn.addEventListener('click', () => loadTree(true));
    expandAllBtn.addEventListener('click', expandAll);
    collapseAllBtn.addEventListener('click', collapseAll);

    // 搜索防抖
    let searchTimer = null;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { filterTree(e.target.value); }, 200);
    });

    // 单独查看按钮
    openInNewPageBtn.addEventListener('click', () => {
        if (currentFileId) {
            window.open(`/view/${currentFileId}`, '_blank');
        }
    });

    // PDF 翻页
    previewPrevPage.addEventListener('click', () => goToPage(currentPage - 1));
    previewNextPage.addEventListener('click', () => goToPage(currentPage + 1));
    previewCurrentPage.addEventListener('change', (e) => goToPage(parseInt(e.target.value)));
    previewCurrentPage.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') goToPage(parseInt(e.target.value));
    });

    // PDF 缩放
    previewZoomIn.addEventListener('click', () => setScale(currentScale * 1.25));
    previewZoomOut.addEventListener('click', () => setScale(currentScale / 1.25));
    previewFitPage.addEventListener('click', fitToPage);

    // 画笔事件
    previewPenToggle.addEventListener('click', togglePen);
    previewPenEraser.addEventListener('click', toggleEraser);
    previewPenClear.addEventListener('click', clearDrawing);
    previewPenUndo.addEventListener('click', undoDrawing);
    previewEraserSize.addEventListener('change', () => { if (isEraser) updateEraserCursor(); });

    // 颜色预设
    document.querySelectorAll('#previewPenBrushOptions .color-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const color = btn.dataset.color;
            previewPenColor.value = color;
            document.querySelectorAll('#previewPenBrushOptions .color-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // 绘图画布事件
    if (previewDrawingCanvas) {
        previewDrawingCanvas.addEventListener('mousedown', startDrawing);
        previewDrawingCanvas.addEventListener('mousemove', draw);
        previewDrawingCanvas.addEventListener('mouseup', stopDrawing);
        previewDrawingCanvas.addEventListener('mouseout', stopDrawing);
        previewDrawingCanvas.addEventListener('touchstart', startDrawing, { passive: false });
        previewDrawingCanvas.addEventListener('touchmove', draw, { passive: false });
        previewDrawingCanvas.addEventListener('touchend', stopDrawing);
        previewDrawingCanvas.addEventListener('touchcancel', stopDrawing);
    }

    // Markdown 编辑
    previewMdEdit.addEventListener('click', toggleMdEditMode);
    previewMdSave.addEventListener('click', () => saveMdContent(false));

    // 页面离开确认
    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges) {
            e.preventDefault();
            e.returnValue = '有未保存的更改，确定要离开吗？';
            return e.returnValue;
        }
        if (eventSource) eventSource.close();
    });

    // 全局快捷键
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            if (currentDocType === 'markdown' && isEditMode && hasUnsavedChanges) {
                e.preventDefault();
                saveMdContent(false);
            }
        }
    });

    // 窗口大小变化
    window.addEventListener('resize', () => {
        if (pdfDoc) {
            clearTimeout(window.resizeTimer);
            window.resizeTimer = setTimeout(() => { fitToPage(); }, 200);
        }
    });
}

// ============ 初始化 ============

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    loadTree();
    connectEventSource();
});

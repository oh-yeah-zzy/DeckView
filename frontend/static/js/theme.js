/**
 * DeckView 主题管理
 * 支持多种主题模式：自动、亮色、暗色、护眼绿、深蓝海洋、Solarized、暖色复古
 */

(function() {
    'use strict';

    // 主题配置
    const THEME_KEY = 'deckview_theme';
    const THEMES = [
        { id: 'auto', name: '跟随系统', icon: '🌗' },
        { id: 'light', name: '亮色', icon: '☀️' },
        { id: 'dark', name: '暗色', icon: '🌙' },
        { id: 'green', name: '护眼绿', icon: '🌿' },
        { id: 'ocean', name: '深蓝海洋', icon: '🌊' },
        { id: 'solarized', name: 'Solarized', icon: '🔆' },
        { id: 'sepia', name: '暖色复古', icon: '📜' }
    ];

    let menuVisible = false;

    /**
     * 获取当前保存的主题模式
     */
    function getSavedMode() {
        return localStorage.getItem(THEME_KEY) || 'auto';
    }

    /**
     * 保存主题模式
     */
    function saveMode(mode) {
        localStorage.setItem(THEME_KEY, mode);
    }

    /**
     * 获取主题配置
     */
    function getThemeConfig(id) {
        return THEMES.find(t => t.id === id) || THEMES[0];
    }

    /**
     * 应用主题
     */
    function applyTheme(mode) {
        const html = document.documentElement;

        // 移除所有主题属性
        html.removeAttribute('data-theme');

        // 设置主题（auto 模式不设置，让 CSS 媒体查询生效）
        if (mode !== 'auto') {
            html.setAttribute('data-theme', mode);
        }

        // 更新切换按钮状态
        updateToggleButton(mode);
    }

    /**
     * 更新切换按钮显示
     */
    function updateToggleButton(mode) {
        const toggleBtn = document.getElementById('themeToggle');
        if (!toggleBtn) return;

        const config = getThemeConfig(mode);
        toggleBtn.setAttribute('data-mode', mode);
        toggleBtn.textContent = config.icon;
        toggleBtn.title = `当前主题：${config.name}（点击切换）`;
    }

    /**
     * 创建主题选择菜单
     */
    function createThemeMenu() {
        let menu = document.getElementById('themeMenu');
        if (menu) return menu;

        menu = document.createElement('div');
        menu.id = 'themeMenu';
        menu.className = 'theme-menu';
        menu.innerHTML = THEMES.map(theme => `
            <button class="theme-menu-item" data-theme="${theme.id}">
                <span class="theme-icon">${theme.icon}</span>
                <span class="theme-name">${theme.name}</span>
            </button>
        `).join('');

        // 添加样式 - 使用固定的高对比度配色，确保在所有主题下都清晰可见
        const style = document.createElement('style');
        style.textContent = `
            .theme-menu {
                position: fixed;
                bottom: 70px;
                right: 16px;
                background: #2a2a2e;
                border: 1px solid #404044;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                padding: 8px 0;
                z-index: 1001;
                opacity: 0;
                transform: translateY(10px);
                pointer-events: none;
                transition: opacity 0.2s, transform 0.2s;
            }
            .theme-menu.visible {
                opacity: 1;
                transform: translateY(0);
                pointer-events: auto;
            }
            .theme-menu-item {
                display: flex;
                align-items: center;
                gap: 10px;
                width: 100%;
                padding: 10px 16px;
                border: none;
                background: transparent;
                color: #e4e4e7;
                cursor: pointer;
                font-size: 0.9rem;
                text-align: left;
                transition: background 0.15s, color 0.15s;
            }
            .theme-menu-item:hover {
                background: #3a3a3e;
                color: #fff;
            }
            .theme-menu-item.active {
                background: #4a90d9;
                color: #fff;
            }
            .theme-icon {
                font-size: 1.1rem;
                width: 24px;
                text-align: center;
            }
            .theme-name {
                flex: 1;
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(menu);

        // 绑定菜单项点击事件
        menu.querySelectorAll('.theme-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const themeId = item.dataset.theme;
                saveMode(themeId);
                applyTheme(themeId);
                hideMenu();
                showThemeToast(`已切换到：${getThemeConfig(themeId).name}`);
            });
        });

        return menu;
    }

    /**
     * 显示主题菜单
     */
    function showMenu() {
        const menu = createThemeMenu();
        const currentMode = getSavedMode();

        // 更新选中状态
        menu.querySelectorAll('.theme-menu-item').forEach(item => {
            item.classList.toggle('active', item.dataset.theme === currentMode);
        });

        menu.classList.add('visible');
        menuVisible = true;

        // 点击外部关闭菜单
        setTimeout(() => {
            document.addEventListener('click', handleOutsideClick);
        }, 0);
    }

    /**
     * 隐藏主题菜单
     */
    function hideMenu() {
        const menu = document.getElementById('themeMenu');
        if (menu) {
            menu.classList.remove('visible');
        }
        menuVisible = false;
        document.removeEventListener('click', handleOutsideClick);
    }

    /**
     * 处理菜单外部点击
     */
    function handleOutsideClick(e) {
        const menu = document.getElementById('themeMenu');
        const toggleBtn = document.getElementById('themeToggle');
        if (menu && !menu.contains(e.target) && e.target !== toggleBtn) {
            hideMenu();
        }
    }

    /**
     * 切换菜单显示
     */
    function toggleMenu() {
        if (menuVisible) {
            hideMenu();
        } else {
            showMenu();
        }
    }

    /**
     * 显示主题切换提示
     */
    function showThemeToast(message) {
        // 尝试使用页面的 toast 函数
        if (typeof showToast === 'function') {
            showToast(message, 'info');
        } else {
            // 备用方案：使用自定义 toast
            let toast = document.getElementById('themeToast');
            if (!toast) {
                toast = document.createElement('div');
                toast.id = 'themeToast';
                toast.style.cssText = `
                    position: fixed;
                    bottom: 70px;
                    right: 180px;
                    padding: 8px 16px;
                    background: var(--card-bg);
                    color: var(--text-color);
                    border-radius: 6px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                    font-size: 0.9rem;
                    opacity: 0;
                    transition: opacity 0.3s;
                    z-index: 1000;
                `;
                document.body.appendChild(toast);
            }
            toast.textContent = message;
            toast.style.opacity = '1';
            setTimeout(() => {
                toast.style.opacity = '0';
            }, 2000);
        }
    }

    /**
     * 初始化主题系统
     */
    function initTheme() {
        // 应用保存的主题
        const savedMode = getSavedMode();
        applyTheme(savedMode);

        // 绑定切换按钮事件
        const toggleBtn = document.getElementById('themeToggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleMenu();
            });
        }

        // 监听系统主题变化
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
                // 只有在自动模式下才响应系统变化
                if (getSavedMode() === 'auto') {
                    applyTheme('auto');
                }
            });
        }
    }

    // 尽早应用主题，避免闪烁
    (function() {
        const savedMode = localStorage.getItem(THEME_KEY) || 'auto';
        if (savedMode !== 'auto') {
            document.documentElement.setAttribute('data-theme', savedMode);
        }
    })();

    // DOM 加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }

    // 导出到全局
    window.DeckViewTheme = {
        getMode: getSavedMode,
        setMode: function(mode) {
            const config = getThemeConfig(mode);
            if (config) {
                saveMode(mode);
                applyTheme(mode);
            }
        },
        getThemes: function() {
            return THEMES.slice();
        }
    };
})();

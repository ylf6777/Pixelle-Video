// 主题切换：dark ↔ light，同步 localStorage + DOM + 系统偏好
document.addEventListener('alpine:init', () => {
  Alpine.data('themeToggle', () => ({
    isDark: document.documentElement.getAttribute('data-theme') === 'dark',
    toggle() {
      this.isDark = !this.isDark;
      const theme = this.isDark ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('pv-theme', theme);
    },
    get icon() { return this.isDark ? '☀️' : '🌙'; },
    get label() { return this.isDark ? '亮色模式' : '暗色模式'; }
  }));
});

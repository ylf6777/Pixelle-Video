// 工作流浏览器 — 搜索 + 分类筛选（渐进增强：卡片服务端渲染，JS 只做 show/hide）
document.addEventListener('alpine:init', () => {
  Alpine.data('workflowBrowser', () => ({
    query: '',
    activeCategory: '',
    categories: [],

    init() {
      this.categories = window.__CATEGORIES__ || [];
      const params = new URLSearchParams(window.location.search);
      this.activeCategory = params.get('category') || '';
      this.query = params.get('q') || '';
      if (this.activeCategory || this.query) this.filter();
    },

    filter() {
      // 触发 UI 刷新 (matchCard 会重新求值)
      const url = new URL(window.location);
      if (this.activeCategory) url.searchParams.set('category', this.activeCategory);
      else url.searchParams.delete('category');
      if (this.query) url.searchParams.set('q', this.query);
      else url.searchParams.delete('q');
      window.history.replaceState({}, '', url);
    },

    matchCard(wf) {
      if (this.activeCategory && wf.category !== this.activeCategory) return false;
      if (this.query.trim()) {
        const q = this.query.toLowerCase();
        const name = (wf.name || '').toLowerCase();
        const desc = (wf.description || '').toLowerCase();
        const tags = (wf.tags || []).join(' ').toLowerCase();
        if (!name.includes(q) && !desc.includes(q) && !tags.includes(q)) return false;
      }
      return true;
    },

    hasVisible() {
      // 检查是否有任何卡片可见
      const grid = document.getElementById('workflow-grid');
      if (!grid) return true;
      const cards = grid.querySelectorAll('.pv-card:not(.pv-empty)');
      for (const card of cards) {
        if (card.style.display !== 'none' && getComputedStyle(card).display !== 'none') {
          return true;
        }
      }
      return false;
    },

    selectCategory(cat) {
      this.activeCategory = this.activeCategory === cat ? '' : cat;
      this.filter();
    },
  }));
});

// 搜索 + 分类筛选（客户端过滤）
document.addEventListener('alpine:init', () => {
  Alpine.data('searchFilter', (initialCategory = '') => ({
    query: '',
    activeCategory: initialCategory,
    get filteredWorkflows() {
      // 从 window.__WORKFLOWS__ 获取（Jinja2 渲染时注入）
      let items = window.__WORKFLOWS__ || [];
      if (this.activeCategory) {
        items = items.filter(w => w.category === this.activeCategory);
      }
      if (this.query.trim()) {
        const q = this.query.toLowerCase();
        items = items.filter(w =>
          w.name.toLowerCase().includes(q) ||
          (w.description || '').toLowerCase().includes(q) ||
          (w.tags || []).some(t => t.toLowerCase().includes(q))
        );
      }
      return items;
    },
    selectCategory(cat) {
      this.activeCategory = this.activeCategory === cat ? '' : cat;
      // 更新 URL query string
      const url = new URL(window.location);
      if (this.activeCategory) url.searchParams.set('category', this.activeCategory);
      else url.searchParams.delete('category');
      window.history.replaceState({}, '', url);
    }
  }));
});

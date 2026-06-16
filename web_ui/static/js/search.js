// 工作流浏览器 — 搜索 + 分类筛选 + URL 同步
document.addEventListener('alpine:init', () => {
  Alpine.data('workflowBrowser', () => ({
    query: '',
    activeCategory: '',
    all: [],
    filtered: [],
    categories: [],

    init() {
      this.all = window.__WORKFLOWS__ || [];
      this.categories = window.__CATEGORIES__ || [];
      const params = new URLSearchParams(window.location.search);
      this.activeCategory = params.get('category') || '';
      this.query = params.get('q') || '';
      this.filter();
    },

    filter() {
      let items = this.all;
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
      this.filtered = items;
      const url = new URL(window.location);
      if (this.activeCategory) url.searchParams.set('category', this.activeCategory);
      else url.searchParams.delete('category');
      if (this.query) url.searchParams.set('q', this.query);
      else url.searchParams.delete('q');
      window.history.replaceState({}, '', url);
    },

    selectCategory(cat) {
      this.activeCategory = this.activeCategory === cat ? '' : cat;
      this.filter();
    },

    renderCard(wf) {
      const labels = {runninghub:'RunningHub', selfhost:'本地', api:'API', zealman:'Zealman'};
      const label = labels[wf.source] || wf.source;
      const tags = (wf.tags || []).map(t =>
        `<span class="pv-card__tag">${t.replace(/</g,'&lt;')}</span>`
      ).join('');
      const desc = (wf.description || '').replace(/</g,'&lt;');
      const name = (wf.name || '').replace(/</g,'&lt;');
      return `<article class="pv-card" data-source="${wf.source}">
        <div class="pv-card__thumb">
          <div class="pv-card__thumb-placeholder" aria-hidden="true">
            <div class="pv-card__thumb-grad"></div>
          </div>
          <span class="pv-badge pv-badge--${wf.source}">${label}</span>
        </div>
        <div class="pv-card__body">
          <h3 class="pv-card__title">${name}</h3>
          <p class="pv-card__desc">${desc}</p>
          ${tags ? '<div class="pv-card__tags">'+tags+'</div>' : ''}
          <a href="/workflow/${wf.id}" class="pv-btn pv-btn--gradient">使用</a>
        </div>
      </article>`;
    }
  }));
});

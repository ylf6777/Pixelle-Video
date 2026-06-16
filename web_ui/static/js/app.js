// 全局初始化
document.addEventListener('alpine:init', () => {
  // 从 URL 读取初始分类筛选
  const params = new URLSearchParams(window.location.search);
  const initialCat = params.get('category') || '';

  Alpine.store('app', {
    category: initialCat,
    searchQuery: '',
  });
});

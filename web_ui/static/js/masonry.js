// 响应式瀑布流布局 + 入场交错动画 + 滚动时关闭 blur 优化性能
document.addEventListener('alpine:init', () => {
  Alpine.data('masonry', () => ({
    init() {
      this.staggerItems();
      this.handleScroll();
    },
    staggerItems() {
      this.$el.querySelectorAll('.pv-card').forEach((el, i) => {
        el.style.animationDelay = `${i * 50}ms`;
        el.classList.add('pv-card--enter');
      });
    },
    handleScroll() {
      let timer;
      window.addEventListener('scroll', () => {
        this.$el.classList.add('is-scrolling');
        clearTimeout(timer);
        timer = setTimeout(() => this.$el.classList.remove('is-scrolling'), 150);
      }, { passive: true });
    }
  }));
});

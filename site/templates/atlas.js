(() => {
  'use strict';
  let lang = 'zh';
  let activeFilter = 'all';
  try { if (localStorage.getItem('neuroLang') === 'en') lang = 'en'; } catch (_) {}
  const search = document.getElementById('atlasSearch');
  const cards = [...document.querySelectorAll('[data-card]')];
  const groups = [...document.querySelectorAll('.system-group')];
  const filters = [...document.querySelectorAll('[data-filter]')];
  const total = cards.length;
  const normalize = text => text.normalize('NFKC').toLocaleLowerCase().trim();

  function filterCards() {
    const words = normalize(search.value).split(/\s+/).filter(Boolean);
    let visible = 0;
    groups.forEach(group => {
      let groupVisible = 0;
      group.querySelectorAll('[data-card]').forEach(card => {
        const matches = (activeFilter === 'all' || group.dataset.group === activeFilter) && words.every(word => normalize(card.dataset.search).includes(word));
        card.hidden = !matches;
        if (matches) groupVisible++;
      });
      group.hidden = groupVisible === 0;
      visible += groupVisible;
    });
    document.getElementById('resultCount').textContent = lang === 'zh' ? `${visible} / ${total} 個主題` : `${visible} / ${total} topics`;
    document.getElementById('emptyState').hidden = visible !== 0;
    document.querySelectorAll('.planned').forEach(el => { el.hidden = !!search.value || activeFilter !== 'all'; });
  }

  function applyLang() {
    document.documentElement.lang = lang === 'zh' ? 'zh-Hant' : 'en';
    document.querySelectorAll('[data-en][data-zh]').forEach(el => { el.textContent = el.dataset[lang]; });
    const toggle = document.getElementById('langToggle');
    toggle.textContent = lang === 'zh' ? 'EN ↗' : '中文 ↗';
    toggle.setAttribute('aria-label', lang === 'zh' ? 'Switch to English' : '切換成繁體中文');
    search.placeholder = lang === 'zh' ? '搜尋系統、腦區、關鍵字…' : 'Search systems, regions, keywords…';
    search.setAttribute('aria-label', lang === 'zh' ? '搜尋圖譜' : 'Search atlases');
    document.querySelector('.species-switch').setAttribute('aria-label', lang === 'zh' ? '切換物種圖譜' : 'Atlas species');
    document.querySelector('.filters').setAttribute('aria-label', lang === 'zh' ? '依主題分類' : 'Filter atlas topics');
    document.title = `${document.body.dataset.species === 'mouse' ? (lang === 'zh' ? '小鼠腦圖譜' : 'Mouse Atlas') : (lang === 'zh' ? '人類神經圖譜' : 'Human Atlas')} · Neuro Atlas`;
    try { localStorage.setItem('neuroLang', lang); } catch (_) {}
    filterCards();
  }

  filters.forEach(button => button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    filters.forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
    filterCards();
  }));
  search.addEventListener('input', filterCards);
  document.getElementById('clearFilters').addEventListener('click', () => {
    search.value = '';
    filters[0].click();
    search.focus();
  });
  document.getElementById('langToggle').addEventListener('click', () => { lang = lang === 'zh' ? 'en' : 'zh'; applyLang(); });
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !document.activeElement.isContentEditable) {
      event.preventDefault(); search.focus();
    }
    if (event.key === 'Escape' && document.activeElement === search) { search.value = ''; filterCards(); }
  });

  document.querySelectorAll('.hot[data-slug]').forEach(hot => {
    const card = cards.find(item => item.dataset.card === hot.dataset.slug);
    if (!card) return;
    function highlight(on) { hot.classList.toggle('on', on); card.classList.toggle('on', on); }
    [hot, card].forEach(el => {
      el.addEventListener('mouseenter', () => highlight(true));
      el.addEventListener('mouseleave', () => highlight(false));
      el.addEventListener('focus', () => highlight(true));
      el.addEventListener('blur', () => highlight(false));
    });
    // The visible card is the canonical address, including preserved legacy paths.
    hot.setAttribute('href', card.getAttribute('href'));
  });
  applyLang();
})();

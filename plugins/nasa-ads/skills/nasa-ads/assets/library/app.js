'use strict';
const $ = selector => document.querySelector(selector);
const roles = {review: '综述', intro: '引言', methods: '方法', discussion: '讨论', comparison: '结果比较'};
const levels = {full: '完整阅读', visual: '完整视觉阅读', targeted: '局部阅读', abstract: '摘要记录', metadata: '题录记录'};
const state = {query: '', collection: '', role: '', tag: '', yearFrom: '', yearTo: '', uncategorized: false, offset: 0, count: 0, limit: 30, selected: new Set(), page: [], expanded: new Set(), active: null, detailTab: 0, request: 0, detailRequest: 0, libraryDir: ''};
const emptyReader = $('#reader').firstElementChild.cloneNode(true);
let restoreRequest = 0;
let noticeTimer;
const collectionDescriptions = new Map();
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
function notice(text) {
  $('#notice').textContent = text;
  $('#notice').hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { $('#notice').hidden = true; }, 5000);
}
async function api(path) {
  const response = await fetch(path, {credentials: 'same-origin'});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '读取失败，请重试。');
  return data;
}
function externalLink(label, url) {
  const link = el('a', label);
  try { if (!['https:', 'http:'].includes(new URL(url).protocol)) return el('span', label); }
  catch { return el('span', label); }
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}
function downloadLink(label, url) {
  const link = el('a', label);
  link.href = url;
  return link;
}
function updateExport() {
  $('#export').disabled = state.selected.size === 0;
  $('#export').textContent = state.selected.size ? `导出所选 (${state.selected.size})` : '导出所选';
  $('#clear-selection').hidden = !state.selected.size;
  const checked = state.page.filter(id => state.selected.has(id)).length;
  $('#select-page').checked = state.page.length > 0 && checked === state.page.length;
  $('#select-page').indeterminate = checked > 0 && checked < state.page.length;
  $('#select-page').disabled = !state.page.length;
}
function browseParams() {
  const params = new URLSearchParams({query: state.query, scope: $('#scope').value, sort: $('#sort').value});
  for (const key of ['collection', 'role', 'tag']) if (state[key]) params.set(key, state[key]);
  if (state.uncategorized) params.set('uncategorized', '1');
  if ($('#status').value) params.set('status', $('#status').value);
  if (state.yearFrom) params.set('year_from', state.yearFrom);
  if (state.yearTo) params.set('year_to', state.yearTo);
  return params;
}
function syncLocation(mode = 'push') {
  if (!mode) return;
  const url = new URL(location.href);
  const params = browseParams();
  for (const [key, value] of [['query', ''], ['scope', 'all'], ['sort', 'year-desc']]) if (params.get(key) === value) params.delete(key);
  if (state.offset) params.set('offset', state.offset);
  if (state.active && state.detailTab) params.set('view', state.detailTab);
  url.search = params.toString();
  url.hash = state.active ? 'paper=' + state.active : '';
  if (url.href !== location.href) history[mode === 'replace' ? 'replaceState' : 'pushState'](null, '', url);
}
function yearError() {
  const from = $('#year-from'), to = $('#year-to');
  for (const field of [from, to]) if (field.validity.badInput || (field.value && (!/^\d{1,4}$/.test(field.value) || Number(field.value) < 1))) return '年份需要填写 1 至 9999 之间的整数。';
  return from.value && to.value && Number(from.value) > Number(to.value) ? '起始年需要小于或等于截止年。请调整年份范围。' : '';
}
function yearFeedback(message = '') {
  $('#year-feedback').textContent = message || '调整范围后，点击应用年份。';
  $('#year-feedback').classList.toggle('invalid', !!message);
  for (const field of ['#year-from', '#year-to']) $(field).setAttribute('aria-invalid', String(!!message));
}
function applyYears() {
  const error = yearError(); yearFeedback(error);
  if (error) { $('.year-filter').open = true; return false; }
  state.yearFrom = $('#year-from').value ? String(Number($('#year-from').value)) : '';
  state.yearTo = $('#year-to').value ? String(Number($('#year-to').value)) : '';
  $('.year-filter').open = false;
  return true;
}
function clearYears() {
  state.yearFrom = ''; state.yearTo = ''; $('#year-from').value = ''; $('#year-to').value = '';
  yearFeedback(); state.offset = 0; loadList();
}
async function restoreLocation() {
  const restore = ++restoreRequest;
  const params = new URLSearchParams(location.search);
  closeNavigation(); closeReader({cancelRestore: false});
  for (const key of ['query', 'collection', 'tag']) state[key] = params.get(key) || '';
  state.role = Object.hasOwn(roles, params.get('role')) ? params.get('role') : '';
  state.uncategorized = params.get('uncategorized') === '1';
  state.offset = /^\d{1,8}$/.test(params.get('offset') || '') ? Number(params.get('offset')) : 0;
  $('#query').value = state.query;
  for (const [id, fallback] of [['scope', 'all'], ['status', ''], ['sort', 'year-desc']]) {
    const select = $('#' + id), value = params.get(id);
    select.value = [...select.options].some(option => option.value === value) ? value : fallback;
  }
  for (const [key, id, param] of [['yearFrom', 'year-from', 'year_from'], ['yearTo', 'year-to', 'year_to']]) {
    const value = params.get(param) || '';
    state[key] = /^[1-9]\d{0,3}$/.test(value) ? value : '';
    $('#' + id).value = state[key];
  }
  const error = yearError(); yearFeedback(error);
  if (error) { state.yearFrom = ''; state.yearTo = ''; $('.year-filter').open = true; }
  const pieces = state.collection.split('/');
  for (let i = 1; i < pieces.length; i++) state.expanded.add(pieces.slice(0, i).join('/'));
  const paper = location.hash.match(/^#paper=(\d+)$/);
  const detailTab = /^[0-3]$/.test(params.get('view') || '') ? Number(params.get('view')) : 0;
  await refresh({historyMode: null});
  if (restore !== restoreRequest) return;
  if (paper) await openPaper(Number(paper[1]), {historyMode: 'replace', detailTab});
  else syncLocation('replace');
}
function navigateTopic(path) { state.collection = path; state.uncategorized = false; state.offset = 0; closeNavigation(); closeReader(); loadList(); }
function closeNavigation() { document.body.classList.remove('nav-open'); $('#nav-backdrop').hidden = true; $('#navigation-toggle').setAttribute('aria-expanded', 'false'); }
function closeReader({cancelRestore = true} = {}) {
  if (cancelRestore) ++restoreRequest;
  ++state.detailRequest;
  state.active = null; state.detailTab = 0;
  $('.layout').classList.remove('reading-open', 'focus-reading');
  $('#reader').replaceChildren(emptyReader.cloneNode(true));
  document.querySelectorAll('.paper-row.selected').forEach(row => row.classList.remove('selected'));
}
function resetFilters() {
  Object.assign(state, {query: '', collection: '', role: '', tag: '', yearFrom: '', yearTo: '', uncategorized: false, offset: 0});
  $('#query').value = ''; $('#scope').value = 'all'; $('#status').value = ''; $('#year-from').value = ''; $('#year-to').value = '';
  yearFeedback(); $('.year-filter').open = false; closeReader(); closeNavigation(); loadList();
}
function navState() {
  $('#all').classList.toggle('active', !state.collection && !state.role && !state.tag && !state.uncategorized);
  $('#uncategorized').classList.toggle('active', state.uncategorized);
  document.querySelectorAll('[data-collection]').forEach(node => node.classList.toggle('active', node.dataset.collection === state.collection));
  document.querySelectorAll('[data-role]').forEach(node => node.classList.toggle('active', node.dataset.role === state.role));
  $('#view-title').textContent = state.collection?.split('/').pop() || (state.uncategorized ? '待分类文献' : state.role ? roles[state.role] + '参考文献' : state.tag ? '标签：' + state.tag : '全部文献');
  $('#breadcrumb').textContent = state.collection.includes('/') ? state.collection.split('/').slice(0, -1).join(' / ') : '文献总览';
  const description = collectionDescriptions.get(state.collection) || '';
  $('#collection-summary').textContent = description;
  $('#collection-summary').hidden = !description;
  const filters = $('#active-filters'); filters.replaceChildren();
  for (const [key, label] of [['collection', state.collection], ['role', roles[state.role]], ['tag', state.tag], ['query', state.query]]) {
    if (!label) continue;
    const chip = el('button', label + ' ×', 'filter-chip');
    chip.setAttribute('aria-label', '移除筛选：' + label);
    chip.addEventListener('click', () => { state[key] = ''; if (key === 'query') $('#query').value = ''; state.offset = 0; loadList(); });
    filters.append(chip);
  }
  const extra = [];
  if (state.yearFrom || state.yearTo) extra.push([`年份：${state.yearFrom || '不限'}–${state.yearTo || '不限'}`, clearYears]);
  if ($('#status').value) extra.push([`阅读：${$('#status').selectedOptions[0].textContent}`, () => { $('#status').value = ''; state.offset = 0; loadList(); }]);
  if (state.query && $('#scope').value !== 'all') extra.push([`范围：${$('#scope').selectedOptions[0].textContent}`, () => { $('#scope').value = 'all'; state.offset = 0; loadList(); }]);
  for (const [label, action] of extra) {
    const chip = el('button', label + ' ×', 'filter-chip'); chip.setAttribute('aria-label', '移除筛选：' + label);
    chip.addEventListener('click', action); filters.append(chip);
  }
  if (filters.children.length || state.uncategorized) {
    const clear = el('button', '清除筛选', 'text-button'); clear.addEventListener('click', resetFilters); filters.append(clear);
  }
}
async function loadList({historyMode = 'push'} = {}) {
  if (historyMode === 'push') ++restoreRequest;
  const request = ++state.request;
  const params = browseParams(); params.set('offset', state.offset); params.set('limit', state.limit);
  $('#papers').setAttribute('aria-busy', 'true');
  $('#export-view').disabled = true;
  $('#list-feedback').hidden = true;
  navState();
  try {
    const data = await api('/api/papers?' + params);
    if (request !== state.request) return;
    if (data.count && state.offset >= data.count) {
      state.offset = Math.floor((data.count - 1) / state.limit) * state.limit;
      return loadList({historyMode: 'replace'});
    }
    state.count = data.count;
    state.page = data.results.map(item => item.paper_id);
    $('#result-count').textContent = `${data.count} 篇文献`;
    $('#papers').replaceChildren();
    if (!data.results.length) {
      const filtered = state.query || state.collection || state.role || state.tag || $('#status').value || state.yearFrom || state.yearTo;
      const message = filtered ? '当前条件下没有文献。调整关键词或筛选条件后继续查找。' : state.uncategorized ? '全部文献均已分类。新增文献需要整理时，会出现在这里。' : '文献库准备就绪。通过 NASA ADS skill 检索后，文章会出现在这里。';
      $('#papers').append(el('p', message, 'empty'));
    }
    for (const item of data.results) {
      const row = el('article', null, 'paper-row' + (state.active === item.paper_id ? ' selected' : ''));
      row.dataset.paperId = item.paper_id;
      const checkbox = el('input');
      checkbox.type = 'checkbox';
      checkbox.checked = state.selected.has(item.paper_id);
      checkbox.setAttribute('aria-label', '选择引用：' + item.title);
      checkbox.addEventListener('change', () => { checkbox.checked ? state.selected.add(item.paper_id) : state.selected.delete(item.paper_id); updateExport(); });
      const open = el('button', null, 'paper-open');
      open.append(el('h3', item.title, 'paper-title'));
      const authors = item.authors.slice(0, 2).join('; ') + (item.authors.length > 2 ? ' et al.' : '');
      open.append(el('p', [item.year, authors, item.pub].filter(Boolean).join(' · '), 'paper-meta'));
      let label = levels[item.reading_status] || item.reading_status;
      if (['abstract', 'metadata'].includes(item.reading_status) && item.brief?.summary_status === 'pending') label += ' · 待总结';
      if (item.tags.includes('已撤回')) open.append(el('span', '已撤回 · 查看来源修正', 'caution'));
      open.append(el('span', label, 'level'));
      const summary = item.snippet || item.brief?.summary || '';
      if (summary) open.append(el('p', summary, 'paper-summary'));
      if (item.collections.length) open.append(el('p', item.collections.slice(0, 2).map(path => path.split('/').slice(-1)[0]).join(' · ') + (item.collections.length > 2 ? ` · +${item.collections.length - 2} 个主题` : ''), 'paper-context'));
      open.addEventListener('click', () => openPaper(item.paper_id));
      row.append(checkbox, open);
      $('#papers').append(row);
    }
    $('#previous').disabled = state.offset === 0;
    $('#next').disabled = state.offset + state.limit >= data.count;
    $('#page-label').textContent = data.count ? `${state.offset + 1}–${Math.min(state.offset + state.limit, data.count)} / ${data.count}` : '0 / 0';
    $('#export-view').disabled = !data.count || data.count > 2000;
    updateExport();
    navState();
    syncLocation(historyMode);
  } catch (error) {
    if (request === state.request) {
      $('#list-feedback').textContent = '文献列表加载失败。当前显示上次成功读取的内容，点击刷新可重试。';
      $('#list-feedback').hidden = false;
    }
  }
  finally { if (request === state.request) $('#papers').removeAttribute('aria-busy'); }
}
function sourceAbstract(container, text) {
  container.append(el('h3', '来源摘要'));
  const paragraph = el('p');
  let parent = paragraph;
  const decode = value => value.replace(/&#(x[0-9a-f]+|[0-9]+);|&(amp|lt|gt|quot|apos|nbsp);/gi, (match, numeric, named) => {
    if (numeric) { const code = numeric[0].toLowerCase() === 'x' ? parseInt(numeric.slice(1), 16) : Number(numeric); return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : match; }
    return {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' '}[named.toLowerCase()];
  });
  for (const piece of text.split(/(<\/?(?:sup|sub)>)/gi)) {
    if (/^<(sup|sub)>$/i.test(piece)) { const node = el(piece.slice(1, -1).toLowerCase()); parent.append(node); parent = node; }
    else if (/^<\/(sup|sub)>$/i.test(piece)) parent = paragraph;
    else parent.append(document.createTextNode(decode(piece.replace(/<[^>]*>/g, ' '))));
  }
  container.append(paragraph);
}
function paragraph(container, title, text) {
  if (!text) return;
  if (title) container.append(el('h3', title));
  container.append(el('p', text));
}
function lines(container, title, values) {
  if (!values?.length) return;
  if (title) container.append(el('h3', title));
  const list = el('ul');
  for (const value of values) list.append(el('li', value));
  container.append(list);
}
async function openPaper(id, {historyMode = 'push', detailTab = 0} = {}) {
  if (historyMode === 'push') ++restoreRequest;
  const request = ++state.detailRequest;
  try {
    const data = await api('/api/paper?id=' + id);
    if (request !== state.detailRequest) return;
    state.active = id;
    state.detailTab = detailTab;
    document.querySelectorAll('.paper-row').forEach(row => row.classList.toggle('selected', Number(row.dataset.paperId) === id));
    const reader = $('#reader');
    reader.replaceChildren();
    const toolbar = el('div', null, 'reader-toolbar');
    const back = el('button', '← 返回文献列表', 'subtle back-button');
    back.addEventListener('click', () => { closeReader(); syncLocation(); $('#query').focus(); });
    const focus = el('button', '专注阅读', 'subtle focus-button');
    focus.addEventListener('click', () => { const on = $('.layout').classList.toggle('focus-reading'); focus.textContent = on ? '恢复分栏' : '专注阅读'; });
    const permalink = el('button', '复制文献链接', 'subtle');
    permalink.addEventListener('click', async () => { try { await navigator.clipboard.writeText(location.href); notice('文献链接已复制，可在本机打开。'); } catch { notice('浏览器暂未允许复制。'); } });
    toolbar.append(back, focus, permalink); reader.append(toolbar);
    const version = data.versions.find(item => item.id === data.preferred_version_id) || data.versions[0];
    const digest = version?.digest?.digest;
    if (data.tags.includes('已撤回')) paragraph(reader, '', '此论文已撤回。阅读总结保留原报告及后续源身份修正，请核对相关更正记录。');
    reader.append(el('span', digest ? levels[digest.reading.status] : levels[data.brief?.evidence_level || 'metadata'], 'level'));
    reader.append(el('h2', data.paper.title, 'article-title'));
    reader.append(el('p', data.paper.authors.slice(0, 5).join('; ') + (data.paper.authors.length > 5 ? ' et al.' : ''), 'authors'));
    if (data.paper.authors.length > 5) {
      const authors = el('details', null, 'all-authors');
      authors.append(el('summary', `查看全部 ${data.paper.authors.length} 位作者`), el('p', data.paper.authors.join('; ')));
      reader.append(authors);
    }
    reader.append(el('p', [data.paper.year, data.paper.pub, data.paper.bibcode].filter(Boolean).join(' · '), 'paper-meta'));
    const links = el('div', null, 'source-links');
    if (data.paper.bibcode) links.append(externalLink('ADS 原始记录 ↗', 'https://ui.adsabs.harvard.edu/abs/' + encodeURIComponent(data.paper.bibcode)));
    const doi = data.paper.identifiers.find(item => item.kind === 'doi');
    const arxiv = data.paper.identifiers.find(item => item.kind === 'arxiv');
    if (doi) links.append(externalLink('DOI ↗', 'https://doi.org/' + encodeURIComponent(doi.value)));
    if (arxiv) links.append(externalLink('arXiv ↗', 'https://arxiv.org/abs/' + arxiv.value));
    reader.append(links);
    const tabs = el('div', null, 'tabs');
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', '文献详情栏目');
    const content = el('div', null, 'detail-content');
    content.id = 'detail-panel';
    content.setAttribute('role', 'tabpanel');
    const views = {
      '概览': () => {
        if (digest) {
          paragraph(content, '论文总结', digest.overview.summary);
          paragraph(content, '研究意义', digest.overview.significance);
          lines(content, '研究问题', digest.overview.questions);
          lines(content, '适用范围与局限', digest.global_limitations);
          lines(content, '主要方法', digest.methods.map(item => [item.name, item.description, item.purpose].filter(Boolean).join(' · ')));
        } else if (data.brief?.summary) {
          paragraph(content, data.brief.evidence_level === 'abstract' ? '基于摘要的总结' : '基于题录的记录', data.brief.summary);
        } else paragraph(content, '总结状态', '题录与来源已经保存，阅读总结等待补写。');
        if (data.brief?.source.abstract || data.paper.abstract) {
          const abstract = el('details'); abstract.append(el('summary', '原始摘要'));
          sourceAbstract(abstract, data.brief?.source.abstract || data.paper.abstract); content.append(abstract);
        }
        if (data.collections.length) {
          content.append(el('h3', '相关主题'));
          const topics = el('div', null, 'topic-links');
          for (const path of data.collections) { const button = el('button', path.split('/').slice(-2).join(' / ')); button.title = path; button.addEventListener('click', () => navigateTopic(path)); topics.append(button); }
          content.append(topics);
        }
        lines(content, '写作用途', data.roles.map(role => roles[role] || role));
        if (data.tags.length) {
          content.append(el('h3', '检索标签')); const tags = el('div', null, 'tag-links');
          for (const value of data.tags) { const tag = el('button', value); tag.addEventListener('click', () => { state.tag = value; state.offset = 0; closeReader(); loadList(); }); tags.append(tag); }
          content.append(tags);
        }
        lines(content, '个人笔记', data.notes.map(note => note.text));
      },
      '科学维度': () => {
        if (!digest) { paragraph(content, '', '完整阅读后，这里会展示可复用的研究维度、结果和证据位置。'); return; }
        const toggle = el('button', '展开全部维度', 'text-button'); let expanded = false;
        toggle.addEventListener('click', () => { expanded = !expanded; content.querySelectorAll('details').forEach(item => { item.open = expanded; }); toggle.textContent = expanded ? '收起全部维度' : '展开全部维度'; }); content.append(toggle);
        for (const facet of digest.facets) {
          const details = el('details');
          details.open = digest.facets.length <= 3;
          details.append(el('summary', facet.label));
          paragraph(details, '', facet.summary);
          for (const finding of facet.findings) {
            const block = el('div', null, 'finding');
            block.append(el('p', finding.statement));
            const locator = Object.entries(finding.locator).filter(([, value]) => value).map(([key, value]) => `${key}: ${value}`).join(' · ');
            const kinds = {measurement: '测量', result: '结果', interpretation: '作者解释', prediction: '模型预测', constraint: '约束', method: '方法', limitation: '局限', observation: '观测', upper_limit: '上限'};
            const confidence = {high: '高可信度', medium: '中等可信度', low: '低可信度'};
            block.append(el('div', `${kinds[finding.kind] || finding.kind} · ${confidence[finding.confidence] || finding.confidence} · ${locator}`, 'locator'));
            for (const value of finding.values) block.append(el('div', [value.name, value.value, value.unit, value.uncertainty, value.qualifier].filter(item => item !== undefined && item !== null).join(' '), 'locator'));
            details.append(block);
          }
          lines(details, '局限', facet.limitations);
          content.append(details);
        }
      },
      '引用': () => {
        paragraph(content, '引用键', data.citation.citekey);
        paragraph(content, '来源', data.citation.source === 'ads' ? 'ADS 官方 BibTeX，已保存在本地。' : '根据本地题录生成。投稿前可获取 ADS 官方条目，核对期刊、卷号与页码。');
        const copy = el('button', '复制 BibTeX');
        copy.addEventListener('click', async () => {
          try { await navigator.clipboard.writeText(data.citation.bibtex); notice('BibTeX 已复制。'); }
          catch { notice('复制功能暂不可用，可选中下方文本或下载引用。'); }
        });
        content.append(copy, el('pre', data.citation.bibtex));
        content.append(downloadLink('下载这篇文献的 .bib 文件', '/api/citations?ids=' + id));
      },
      '全文版本': () => {
        if (!data.versions.length) { paragraph(content, '', '当前保存了题录与摘要。阅读全文后会保存对应的文章文件、版本和阅读范围。'); return; }
        for (const item of data.versions) {
          paragraph(content, `${item.version_kind} · ${item.format}${item.id === data.preferred_version_id ? ' · 当前优先版本' : ''}`, `保存时间：${item.retrieved_at || '未记录'}`);
          const actions = el('div', null, 'source-links');
          actions.append(downloadLink('下载文章文件', `/api/artifact?version=${item.id}&kind=article`));
          if (item.text_path) actions.append(downloadLink('下载提取文本', `/api/artifact?version=${item.id}&kind=text`));
          content.append(actions);
          const reading = item.digest?.digest?.reading;
          if (reading) lines(content, '阅读章节', reading.sections);
          if (reading?.visual_page_ranges.length) paragraph(content, '视觉阅读页码', reading.visual_page_ranges.join(', '));
          paragraph(content, '内容指纹', item.content_sha256);
        }
      }
    };
    let initializing = true;
    function activate(button, render, index) {
      tabs.querySelectorAll('button').forEach(node => { const active = node === button; node.classList.toggle('active', active); node.setAttribute('aria-selected', active); node.tabIndex = active ? 0 : -1; });
      content.setAttribute('aria-labelledby', button.id);
      content.replaceChildren(); render();
      state.detailTab = index;
      if (!initializing) syncLocation('replace');
    }
    Object.entries(views).forEach(([label, render], index) => {
      const button = el('button', label);
      button.id = 'reader-tab-' + index;
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-controls', 'detail-panel');
      button.addEventListener('click', () => activate(button, render, index));
      button.addEventListener('keydown', event => {
        const buttons = [...tabs.children];
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
          buttons[next].click(); buttons[next].focus();
        }
      });
      tabs.append(button);
    });
    reader.append(tabs, content);
    (tabs.children[detailTab] || tabs.firstElementChild).click();
    initializing = false;
    reader.scrollTop = 0;
    $('.layout').classList.add('reading-open');
    if (window.innerWidth <= 1100) reader.focus();
    syncLocation(historyMode);
  } catch (error) { notice(error.message); }
}
function folderNodes(nodes, parent) {
  for (const item of nodes) {
    collectionDescriptions.set(item.path, item.description);
    const row = el('div', null, 'folder-row');
    const button = el('button', null, 'nav-button');
    button.dataset.collection = item.path;
    const label = el('span', null, 'folder-label');
    label.append(el('span', item.name), el('span', item.count, 'folder-count'));
    button.append(label);
    button.addEventListener('click', () => navigateTopic(item.path));
    parent.append(row);
    if (item.children.length) {
      const toggle = el('button', '›', 'folder-toggle');
      const child = el('div', null, 'folder-children'); child.hidden = !state.expanded.has(item.path);
      toggle.setAttribute('aria-label', '展开或收起：' + item.name); toggle.setAttribute('aria-expanded', !child.hidden);
      toggle.addEventListener('click', () => { child.hidden = !child.hidden; toggle.setAttribute('aria-expanded', !child.hidden); child.hidden ? state.expanded.delete(item.path) : state.expanded.add(item.path); });
      row.append(toggle, button); folderNodes(item.children, child); parent.append(child);
    } else row.append(el('span', null, 'folder-spacer'), button);
  }
}
async function refresh({historyMode = 'replace'} = {}) {
  try {
    const [stats, tree] = await Promise.all([api('/api/stats'), api('/api/collections')]);
    $('#stats').textContent = `${stats.counts.papers} 篇文献 · ${stats.counts.complete_digests} 份全文总结` + (stats.pending_summaries ? ` · ${stats.pending_summaries} 待总结` : '');
    $('#all-count').textContent = stats.counts.papers;
    $('#uncategorized-count').textContent = stats.uncategorized;
    $('#library-label').textContent = '本地文献库';
    $('#library-info').title = stats.library_dir;
    $('#library-details').textContent = `${stats.counts.papers} 篇文献 · ${stats.counts.versions} 个全文版本\n${stats.counts.complete_digests} 份全文总结 · ${stats.counts.citations} 份已缓存引用\n\n存储位置\n${stats.library_dir}\n\n浏览方式：只读`;
    if (state.libraryDir && state.libraryDir !== stats.library_dir) { state.selected.clear(); state.active = null; closeReader(); }
    state.libraryDir = stats.library_dir;
    document.querySelectorAll('[data-role]').forEach(button => { button.querySelector('.nav-count').textContent = stats.roles[button.dataset.role] || 0; });
    $('#collections').replaceChildren();
    collectionDescriptions.clear();
    folderNodes([...tree.collections].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh-CN')), $('#collections'));
    if (!tree.count) $('#collections').append(el('p', '分类会随文献整理逐步建立。', 'muted'));
    await loadList({historyMode});
  } catch (error) {
    $('#stats').textContent = '文献库读取失败';
    $('#list-feedback').textContent = '文献库连接失败。请确认本地服务已启动，再点击刷新。';
    $('#list-feedback').hidden = false;
    $('#export-view').disabled = true;
  }
}
for (const [value, label] of Object.entries(roles)) {
  const button = el('button', null, 'nav-button');
  button.append(el('span', label), el('span', '', 'nav-count'));
  button.dataset.role = value;
  button.addEventListener('click', () => { state.role = state.role === value ? '' : value; state.offset = 0; closeNavigation(); closeReader(); loadList(); });
  $('#roles').append(button);
}
$('#all').addEventListener('click', resetFilters);
$('#uncategorized').addEventListener('click', () => { state.collection = ''; state.role = ''; state.tag = ''; state.uncategorized = true; state.offset = 0; closeNavigation(); closeReader(); loadList(); });
$('#search-form').addEventListener('submit', event => { event.preventDefault(); if (!applyYears()) return; state.query = $('#query').value.trim(); state.offset = 0; closeReader(); loadList(); });
for (const selector of ['#scope', '#status', '#sort']) $(selector).addEventListener('change', () => { state.offset = 0; closeReader(); loadList(); });
for (const selector of ['#year-from', '#year-to']) $(selector).addEventListener('input', () => yearFeedback(yearError()));
$('#apply-years').addEventListener('click', () => { if (applyYears()) { state.offset = 0; closeReader(); loadList(); } });
$('#clear-years').addEventListener('click', clearYears);
$('#previous').addEventListener('click', () => { state.offset = Math.max(0, state.offset - state.limit); loadList(); $('#workspace').scrollTop = 0; });
$('#next').addEventListener('click', () => { state.offset += state.limit; loadList(); $('#workspace').scrollTop = 0; });
$('#refresh').addEventListener('click', () => refresh());
$('#export').addEventListener('click', () => { if (state.selected.size) window.location.assign('/api/citations?ids=' + [...state.selected].join(',')); });
$('#export-view').addEventListener('click', () => { const params = browseParams(); params.set('view', 'filtered'); window.location.assign('/api/citations?' + params); });
$('#select-page').addEventListener('change', event => { for (const id of state.page) event.target.checked ? state.selected.add(id) : state.selected.delete(id); document.querySelectorAll('.paper-row > input').forEach(input => { input.checked = state.selected.has(Number(input.parentElement.dataset.paperId)); }); updateExport(); });
$('#clear-selection').addEventListener('click', () => { state.selected.clear(); document.querySelectorAll('.paper-row > input').forEach(input => { input.checked = false; }); updateExport(); });
$('#collapse-tree').addEventListener('click', () => { state.expanded.clear(); document.querySelectorAll('.folder-children').forEach(child => { child.hidden = true; }); document.querySelectorAll('.folder-toggle').forEach(button => button.setAttribute('aria-expanded', 'false')); });
$('#navigation-toggle').addEventListener('click', () => { closeReader(); syncLocation(); const open = document.body.classList.toggle('nav-open'); $('#nav-backdrop').hidden = !open; $('#navigation-toggle').setAttribute('aria-expanded', open); });
$('#nav-backdrop').addEventListener('click', closeNavigation);
$('#library-info').addEventListener('click', () => $('#library-dialog').showModal());
$('#close-library-dialog').addEventListener('click', () => $('#library-dialog').close());
document.addEventListener('keydown', event => {
  if ($('#library-dialog').open) return;
  if (event.key === '/' && !event.ctrlKey && !event.metaKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) {
    event.preventDefault(); closeReader(); closeNavigation(); syncLocation(); $('#query').focus();
  }
  if (event.key === 'Escape') {
    if ($('.year-filter').open) { $('.year-filter').open = false; $('.year-filter summary').focus(); }
    else { closeNavigation(); closeReader(); syncLocation(); $('#query').focus(); }
  }
});
window.addEventListener('popstate', restoreLocation);
restoreLocation();

'use strict';
const data = JSON.parse(document.getElementById('report-data').textContent);
const $ = selector => document.querySelector(selector);
const drawer = $('#drawer');
let lastFocus = null;
const templates = new Map([...document.querySelectorAll('template[data-finding]')].map(t => [t.dataset.finding, t]));
document.querySelectorAll('.finding').forEach(button => button.addEventListener('click', () => {
  lastFocus = button;
  $('#drawer-body').replaceChildren(templates.get(button.dataset.id).content.cloneNode(true));
  drawer.showModal();
  $('#close').focus();
}));
$('#close').addEventListener('click', () => drawer.close());
drawer.addEventListener('close', () => { hideTerm(); lastFocus?.focus(); });

const rows = [...document.querySelectorAll('#finding-rows tr')];
const search = $('#search');
let activeStatus = '';
function filterFindings() {
  const query = search.value.trim().toLocaleLowerCase();
  let count = 0;
  rows.forEach(row => {
    row.hidden = (!!activeStatus && row.dataset.status !== activeStatus) || (!!query && !row.dataset.search.toLocaleLowerCase().includes(query));
    if (!row.hidden) count += 1;
  });
  $('#count').textContent = `显示 ${count} / ${rows.length} 项`;
  $('#empty').hidden = count > 0;
  document.querySelectorAll('[data-status-filter]').forEach(button => {
    const selected = button.dataset.statusFilter === activeStatus;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
}
if (search) {
  search.addEventListener('input', filterFindings);
  document.querySelectorAll('[data-status-filter]').forEach(button => button.addEventListener('click', () => { activeStatus = button.dataset.statusFilter; filterFindings(); }));
  $('#reset').addEventListener('click', () => { activeStatus = ''; search.value = ''; filterFindings(); search.focus(); });
  filterFindings();
}

const resize = $('#resize');
let dragging = false;
function setWidth(width) { document.documentElement.style.setProperty('--drawer-width', Math.max(360, Math.min(1120, innerWidth, width)) + 'px'); }
resize.addEventListener('pointerdown', event => { dragging = true; resize.setPointerCapture(event.pointerId); });
resize.addEventListener('pointermove', event => { if (dragging) setWidth(innerWidth - event.clientX); });
resize.addEventListener('pointerup', () => { dragging = false; });
resize.addEventListener('pointercancel', () => { dragging = false; });
resize.addEventListener('keydown', event => {
  if (['ArrowLeft', 'ArrowRight'].includes(event.key)) {
    event.preventDefault();
    setWidth(drawer.getBoundingClientRect().width + (event.key === 'ArrowLeft' ? 32 : -32));
  }
});

const popover = $('#term-popover');
const termDialog = $('#term-dialog');
let termFocus = null;
let previewTerm = null;
function showTerm(element) {
  const term = (data.glossary || [])[Number(element.dataset.glossary)];
  if (!term) return;
  // Modal dialogs occupy the browser's top layer; tooltip must share it.
  const container = element.closest('dialog') || document.body;
  if (popover.parentElement !== container) container.append(popover);
  const heading = document.createElement('strong');
  heading.className = 'term-preview-title';
  heading.textContent = term.term + (term.full ? ' · ' + term.full : '');
  const description = document.createElement('p');
  description.className = 'term-preview-explanation';
  description.textContent = term.explanation;
  popover.replaceChildren(heading, description);
  if (term.original) {
    const quote = document.createElement('blockquote');
    quote.className = 'term-preview-quote';
    quote.textContent = '原文：' + term.original;
    const source = document.createElement('p');
    source.className = 'term-preview-source';
    const sourceLabel = term.source.split(/[\\/]/).at(-1);
    source.textContent = '出处：' + (sourceLabel.length > 140 ? sourceLabel.slice(0,100) + '…' + sourceLabel.slice(-30) : sourceLabel);
    popover.append(quote, source);
  }
  if (term.scopeNote) {
    const note = document.createElement('p');
    note.className = 'term-preview-scope';
    note.textContent = '边界：' + term.scopeNote;
    popover.append(note);
  }
  const hint = document.createElement('small');
  hint.textContent = '此处为预览；点击原词查看完整原文、出处与依据';
  popover.append(hint);
  previewTerm?.removeAttribute('aria-describedby');
  previewTerm = element;
  element.setAttribute('aria-describedby', 'term-popover');
  popover.hidden = false;
  const rect = element.getBoundingClientRect();
  const box = popover.getBoundingClientRect();
  popover.style.left = Math.max(12, Math.min(innerWidth - box.width - 12, rect.left)) + 'px';
  popover.style.top = Math.max(8, Math.min(innerHeight - box.height - 8, rect.top > box.height + 18 ? rect.top - box.height - 10 : rect.bottom + 10)) + 'px';
}
function hideTerm() { popover.hidden = true; previewTerm?.removeAttribute('aria-describedby'); previewTerm = null; }

document.addEventListener('click', event => {
  const term = event.target.closest?.('a.term');
  if (!term || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const target = document.getElementById(term.getAttribute('href').slice(1));
  if (!target) return;
  event.preventDefault();
  hideTerm();
  termFocus = term;
  const detail = target.cloneNode(true);
  detail.removeAttribute('id');
  $('#term-dialog-body').replaceChildren(detail);
  termDialog.showModal();
  $('#term-close').focus();
});
$('#term-close').addEventListener('click', () => termDialog.close());
termDialog.addEventListener('close', () => { hideTerm(); termFocus?.focus(); termFocus = null; });
document.addEventListener('keydown', event => { if (event.key === 'Escape') hideTerm(); });
document.addEventListener('mouseover', event => { const term = event.target.closest?.('.term'); if (term) showTerm(term); });
document.addEventListener('mouseout', event => { if (event.target.closest?.('.term')) hideTerm(); });
document.addEventListener('focusin', event => { const term = event.target.closest?.('.term'); if (term) showTerm(term); });
document.addEventListener('focusout', event => { if (event.target.closest?.('.term')) hideTerm(); });
addEventListener('resize', hideTerm);
addEventListener('scroll', () => {
  const term = previewTerm || document.activeElement;
  if (!term?.matches('.term')) { hideTerm(); return; }
  const rect = term.getBoundingClientRect();
  if (rect.bottom > 0 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth) showTerm(term);
  else hideTerm();
}, true);

document.documentElement.classList.add('js-enabled');
const folds = [...document.querySelectorAll('details[data-fold]')];
function updateFoldCount() {
  const counter = $('#fold-status');
  if (counter) counter.textContent = `详情已展开 ${folds.filter(fold => fold.open).length} / ${folds.length} 项`;
}
folds.forEach(fold => fold.addEventListener('toggle', updateFoldCount));
document.querySelectorAll('[data-fold-action]').forEach(button => button.addEventListener('click', () => {
  folds.forEach(fold => { fold.open = button.dataset.foldAction === 'expand'; });
  updateFoldCount();
}));
function revealAnchor(hash) {
  let id;
  try { id = decodeURIComponent(hash.slice(1)); } catch { return; }
  const target = document.getElementById(id);
  if (!target) return;
  if (target.tagName === 'DETAILS') target.open = true;
  for (let parent = target.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === 'DETAILS') parent.open = true;
  }
  // Chapter navigation exposes its primary content, leaving optional deeper folds alone.
  target.querySelector(':scope > details[data-primary]')?.setAttribute('open', '');
  updateFoldCount();
  requestAnimationFrame(() => { target.scrollIntoView({block:'start',behavior:'instant'}); updateReadingPosition(); });
}
document.addEventListener('click', event => {
  const link = event.target.closest?.('a[href^="#"]');
  if (!link || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  if (link.closest('#term-dialog') && termDialog.open) { termFocus = null; termDialog.close(); }
  if (link.closest('dialog') && drawer.open) drawer.close();
  revealAnchor(link.getAttribute('href'));
});
addEventListener('hashchange', () => revealAnchor(location.hash));
updateFoldCount();

const chapters = [...document.querySelectorAll('section[data-chapter]')];
const chapterLinks = [...document.querySelectorAll('.nav a')];
let readingFrame = null;
function updateReadingPosition() {
  const line = ($('.report-navigation')?.getBoundingClientRect().height || 0) + 24;
  let current = chapters[0];
  for (const chapter of chapters) {
    if (chapter.getBoundingClientRect().top <= line) current = chapter;
    else break;
  }
  if (!current) return;
  if (scrollY > 0 && innerHeight + scrollY >= document.documentElement.scrollHeight - 2) current = chapters.at(-1);
  const title = current.querySelector('h2')?.textContent.replace(/^\s*[\d.]+\s*/, '') || '';
  $('#reading-position').textContent = `阅读位置 ${current.dataset.chapter} / ${chapters.length} · ${title}`;
  chapterLinks.forEach(link => {
    const active = link.getAttribute('href') === '#'+current.id;
    const changed = active && !link.hasAttribute('aria-current');
    if (active) link.setAttribute('aria-current','location');
    else link.removeAttribute('aria-current');
    if (changed) {
      const nav = link.parentElement;
      const box = link.getBoundingClientRect(), parent = nav.getBoundingClientRect();
      if (box.left < parent.left || box.right > parent.right) nav.scrollLeft += box.left - parent.left - 12;
    }
  });
}
function scheduleReadingPosition() {
  if (readingFrame !== null) return;
  readingFrame = requestAnimationFrame(() => { readingFrame = null; updateReadingPosition(); });
}
addEventListener('scroll',scheduleReadingPosition,{passive:true});
addEventListener('resize',scheduleReadingPosition);
folds.forEach(fold => fold.addEventListener('toggle',scheduleReadingPosition));
updateReadingPosition();
if (location.hash) revealAnchor(location.hash);

let foldState = null;
addEventListener('beforeprint', () => {
  if (foldState) return; // Some print engines dispatch beforeprint twice.
  foldState = [...document.querySelectorAll('details')].map(element => [element, element.open]);
  foldState.forEach(([element]) => { element.open = true; });
});
addEventListener('afterprint', () => { foldState?.forEach(([element, open]) => { element.open = open; }); foldState = null; updateFoldCount(); });

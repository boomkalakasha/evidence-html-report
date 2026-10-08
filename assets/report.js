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
function showTerm(element) {
  const term = (data.glossary || [])[Number(element.dataset.glossary)];
  if (!term) return;
  // Modal dialogs occupy the browser's top layer; tooltip must share it.
  const container = element.closest('dialog') || document.body;
  if (popover.parentElement !== container) container.append(popover);
  const heading = document.createElement('strong');
  heading.textContent = term.term + (term.full ? ' · ' + term.full : '');
  const description = document.createElement('span');
  description.textContent = term.explanation;
  popover.replaceChildren(heading, description);
  popover.hidden = false;
  const rect = element.getBoundingClientRect();
  const box = popover.getBoundingClientRect();
  popover.style.left = Math.max(12, Math.min(innerWidth - box.width - 12, rect.left)) + 'px';
  popover.style.top = Math.max(8, Math.min(innerHeight - box.height - 8, rect.top > box.height + 18 ? rect.top - box.height - 10 : rect.bottom + 10)) + 'px';
}
function hideTerm() { popover.hidden = true; }
document.addEventListener('mouseover', event => { const term = event.target.closest?.('.term'); if (term) showTerm(term); });
document.addEventListener('mouseout', event => { if (event.target.closest?.('.term')) hideTerm(); });
document.addEventListener('focusin', event => { const term = event.target.closest?.('.term'); if (term) showTerm(term); });
document.addEventListener('focusout', event => { if (event.target.closest?.('.term')) hideTerm(); });
addEventListener('resize', hideTerm);
addEventListener('scroll', hideTerm, true);

let foldState = [];
addEventListener('beforeprint', () => {
  foldState = [...document.querySelectorAll('details')].map(element => [element, element.open]);
  foldState.forEach(([element]) => { element.open = true; });
});
addEventListener('afterprint', () => { foldState.forEach(([element, open]) => { element.open = open; }); foldState = []; });

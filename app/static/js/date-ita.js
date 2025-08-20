(function(){
  function toDDMMYYYY(s){
    if (!s) return null;
    const str = String(s).trim();
    const m = /^\s*(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?(?:Z|[+-]\d{2}:?\d{2})?)?\s*$/.exec(str);
    if (!m) return null;
    const ddmmyyyy = m[3] + "/" + m[2] + "/" + m[1];
    if (m[4] && m[5]) { return ddmmyyyy + " " + m[4] + ":" + m[5]; }
    return ddmmyyyy;
  }
  function shouldSkip(el){
    if (!el || el.nodeType !== 1) return true;
    const tn = el.tagName;
    if (tn === 'INPUT' || tn === 'TEXTAREA') return true;
    if (el.isContentEditable) return true;
    if (el.getAttribute('data-itafmt') === '1') return true;
    return false;
  }
  function formatElement(el){
    if (shouldSkip(el)) return false;
    if (el.tagName === 'TIME'){
      const raw = el.getAttribute('datetime') || el.textContent;
      const f = toDDMMYYYY(raw);
      if (f){ el.textContent = f; el.setAttribute('data-itafmt','1'); return true; }
    }
    const attrs = ['data-date','data-datetime','data-iso','datetime'];
    for (const a of attrs){
      if (el.hasAttribute(a)){
        const f = toDDMMYYYY(el.getAttribute(a));
        if (f){ el.textContent = f; el.setAttribute('data-itafmt','1'); return true; }
      }
    }
    const txt = (el.textContent || '').trim();
    if (/^\d{4}-\d{2}-\d{2}/.test(txt)){
      const f = toDDMMYYYY(txt);
      if (f){ el.textContent = f; el.setAttribute('data-itafmt','1'); return true; }
    }
    return false;
  }
  function run(root){
    const scope = root && root.nodeType === 1 ? root : document;
    const nodes = scope.querySelectorAll('time, [datetime], [data-date], [data-datetime], [data-iso], .date, .data, .dt, td, span');
    nodes.forEach(formatElement);
  }
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ run(document); });
  } else {
    run(document);
  }
  const obs = new MutationObserver(function(muts){
    for (const m of muts){
      if (m.addedNodes && m.addedNodes.length){
        m.addedNodes.forEach(node => { if (node.nodeType === 1) run(node); });
      }
    }
  });
  obs.observe(document.documentElement, { childList: true, subtree: true });
  window.formatDateITA = toDDMMYYYY;
})();

// static/js/app.js - helper comuni
window.App = (function(){
  const toastHostId = '__toast_host__';
  function ensureHost(){
    let host = document.getElementById(toastHostId);
    if(!host){
      host = document.createElement('div');
      host.id = toastHostId;
      host.style.position = 'fixed';
      host.style.top = '1rem';
      host.style.right = '1rem';
      host.style.zIndex = '9999';
      document.body.appendChild(host);
    }
    return host;
  }
  function showToast(msg, kind='info', ms=3000){
    const host = ensureHost();
    const el = document.createElement('div');
    el.style.marginTop = '8px';
    el.style.padding = '10px 14px';
    el.style.borderRadius = '10px';
    el.style.boxShadow = '0 4px 12px rgba(0,0,0,.1)';
    el.style.background = kind==='error' ? '#fee2e2' : (kind==='success' ? '#dcfce7' : '#eef2ff');
    el.style.color = kind==='error' ? '#991b1b' : (kind==='success' ? '#166534' : '#3730a3');
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(()=> host.removeChild(el), ms);
  }
  async function fetchJson(url, options={}){
    const res = await fetch(url, { headers: {'Accept':'application/json'}, ...options });
    if(!res.ok){
      let detail='';
      try { const j=await res.json(); detail=j.error || JSON.stringify(j); } catch{}
      throw new Error(detail || res.statusText);
    }
    return res.json();
  }
  function formatEuro(v){
    return new Intl.NumberFormat('it-IT', {style:'currency', currency:'EUR'}).format(Number(v||0));
  }
  function debounce(fn, wait=250){
    let t; return (...args)=>{ clearTimeout(t); t=setTimeout(()=>fn(...args), wait); };
  }
  function setJSON(key, obj){ localStorage.setItem(key, JSON.stringify(obj)); }
  function getJSON(key, def=null){ try{ return JSON.parse(localStorage.getItem(key)) ?? def; } catch{ return def; } }
  return { showToast, fetchJson, formatEuro, debounce, setJSON, getJSON };
})();

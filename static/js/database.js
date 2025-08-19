
// static/js/database.js - wrapper semplice su localStorage
window.DB = {
  get(key, def=null){
    try{ return JSON.parse(localStorage.getItem(key)) ?? def; }catch{ return def; }
  },
  set(key, val){ localStorage.setItem(key, JSON.stringify(val)); },
  remove(key){ localStorage.removeItem(key); },
  push(key, item){
    const arr = this.get(key, []); arr.push(item); this.set(key, arr); return arr;
  }
};

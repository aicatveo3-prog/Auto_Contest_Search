import json

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 공모전 파인더</title>
<style>
  :root{
    --bg:#f7f8fa; --panel:#ffffff; --panel2:#f3f4f6; --text:#1a2032;
    --muted:#6b7280; --line:#e7eaf0; --accent:#3b5bfd;
    --must:#2f54eb; --must-bg:#e7edff;
    --allowed:#047857; --allowed-bg:#e7f6ee;
    --unclear:#92400e; --unclear-bg:#fef3c7;
    --prohibited:#b91c1c; --prohibited-bg:#fde8e8;
    --none:#9ca3af;
    --hot:#d97706; --gold:#b45309; --goldbg:#ffd479; --money:#0f9d58; --warn:#b45309;
    --hotbg:#fef3d8; --hotline:#f0b429;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:"맑은 고딕","Malgun Gothic","Segoe UI",system-ui,-apple-system,sans-serif}
  header{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.94);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:16px 22px 10px}
  .top{display:flex;align-items:baseline;gap:14px;margin-bottom:10px}
  h1{margin:0;font-size:20px;color:#10131f}
  .meta{color:var(--muted);font-size:13px;margin:0}
  .controls{display:flex;gap:10px;align-items:center;margin-bottom:10px}
  input#q{flex:1;min-width:180px;background:var(--panel);border:1px solid var(--line);color:var(--text);padding:9px 12px;border-radius:8px;font-size:14px}
  input#q::placeholder{color:#9ca3af}
  select{background:var(--panel);border:1px solid var(--line);color:var(--text);padding:9px 12px;border-radius:8px;font-size:14px}
  .seg{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel)}
  .seg button{background:var(--panel);border:0;border-right:1px solid var(--line);color:var(--muted);padding:9px 13px;font-size:13px;cursor:pointer}
  .seg button:last-child{border-right:0}
  .seg button.on{background:#eef2ff;color:#2f54eb;font-weight:700}
  .bmseg button{color:#8a6d1f;font-weight:700;font-size:14px;padding:9px 16px;background:#fdf6e3}
  .bmseg{border-color:#e9d8a6;box-shadow:0 1px 3px rgba(212,167,44,.25)}
  .bmseg button.on{background:var(--goldbg);color:#181510}
  .fl{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:6px}
  .fl .lb{font-size:12px;color:var(--muted);width:34px;flex:none;font-weight:600}
  .chip{cursor:pointer;border:1px solid var(--line);background:var(--panel);color:#374151;padding:4px 11px;border-radius:999px;font-size:13px;user-select:none}
  .chip:hover{border-color:var(--accent);color:var(--accent)}
  .chip.active{color:#fff;border-color:var(--accent);background:var(--accent)}
  .chip .n{opacity:.7;margin-left:5px}
  main{padding:18px 22px 60px}
  .count{color:var(--muted);font-size:13px;margin-bottom:10px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
  .gh{font-size:13px;font-weight:700;color:var(--muted);margin:22px 0 10px}
  .gh:first-of-type{margin-top:0}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 15px;display:flex;flex-direction:column;gap:9px;box-shadow:0 1px 3px rgba(16,19,31,.05)}
  .card:hover{border-color:var(--accent);box-shadow:0 2px 8px rgba(59,91,253,.08)}
  .card.hot{border:1.5px solid var(--hotline);box-shadow:0 0 0 3px var(--hotbg)}
  .card.bm{border-color:var(--goldbg);box-shadow:inset 0 0 0 1px var(--goldbg)}
  .card.expired{opacity:.6}
  .row1{display:flex;align-items:center;gap:8px}
  .row1 .dday{margin-right:auto}
  .badge{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px}
  .badge.must{background:var(--must-bg);color:var(--must)}
  .badge.allowed{background:var(--allowed-bg);color:var(--allowed)}
  .badge.unclear{background:var(--unclear-bg);color:var(--unclear)}
  .badge.prohibited{background:var(--prohibited-bg);color:var(--prohibited)}
  .badge.none{border:1px dashed var(--none);color:var(--none)}
  .dday{font-size:13px;font-weight:700;color:#4b5563}
  .dday small{font-weight:400;color:var(--muted);margin-left:6px;font-size:12px}
  .card.hot .dday{color:var(--hot)}
  .card.expired .dday{color:#9ca3af}
  .bm-btn{cursor:pointer;border:1px solid var(--line);background:var(--panel2);color:#9aa0b4;border-radius:8px;font-size:15px;line-height:1;padding:4px 8px}
  .bm-btn:hover{border-color:var(--goldbg);color:var(--gold)}
  .bm-btn.on{background:var(--goldbg);border-color:var(--goldbg);color:#181510;font-weight:700}
  .bar{height:5px;border-radius:999px;background:var(--panel2);overflow:hidden}
  .bar i{display:block;height:100%;background:#c9cfd8;border-radius:999px}
  .card.hot .bar i{background:var(--hotline)}
  h3{margin:0;font-size:15px;line-height:1.35;color:#10131f}
  h3 a{color:var(--text);text-decoration:none} h3 a:hover{text-decoration:underline}
  .sub{font-size:12.5px;color:var(--muted);margin-top:3px}
  .fields{display:flex;flex-direction:column;gap:3px;font-size:12.5px;line-height:1.45}
  .fields .row{display:flex;gap:8px}
  .fields .k{color:#9ca3af;flex:0 0 32px}
  .fields .v{color:#303a4e;flex:1}
  .fields .v.notes{color:var(--warn)}
  .tags{display:flex;gap:6px;flex-wrap:wrap}
  .tag{font-size:11.5px;background:#f7f8fa;border:1px solid var(--line);color:var(--muted);padding:2px 8px;border-radius:999px}
  .prize-box{font-size:12.5px;background:#f9fafb;border:1px solid #eef0f3;border-radius:8px;padding:7px 10px}
  .prize-box .bd-title{color:var(--muted);font-size:11.5px;margin-bottom:4px}
  .prize-box .prow{display:flex;justify-content:space-between;gap:8px;padding:1px 0}
  .prize-box .prow .pr{color:var(--gold);flex:1}
  .prize-box .prow .pc{color:var(--muted);flex:0 0 40px;text-align:right}
  .prize-box .prow .pm{color:var(--money);font-weight:700;flex:0 0 84px;text-align:right}
  .evidence{font-size:12.5px;color:#3c4557;background:#f8faff;border-left:3px solid var(--accent);padding:7px 10px;border-radius:6px;line-height:1.45}
  .links{display:flex;gap:12px;font-size:12.5px;margin-top:2px}
  .links a{color:var(--accent);text-decoration:none;font-weight:600} .links a:hover{text-decoration:underline}
  .lrow{display:grid;grid-template-columns:92px minmax(0,1fr) 90px 110px 34px;gap:10px;align-items:center;padding:9px 6px;border-bottom:1px solid var(--line);font-size:13.5px}
  .lrow:hover{background:#f6f8ff}
  .lrow.expired{opacity:.6}
  .lrow .t{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .lrow .t a{color:var(--text);text-decoration:none} .lrow .t a:hover{text-decoration:underline}
  .lrow .m{text-align:right;color:var(--money);font-weight:700}
  .lrow.hot .dday{color:var(--hot)}
  .empty{color:var(--muted);text-align:center;padding:40px}
</style>
</head>
<body>
<header>
  <div class="top">
    <h1>AI 공모전 파인더</h1>
    <p class="meta">생성 __GENERATED__ · 전체 <b id="total">0</b>건 · 표시 <b id="shown">0</b>건</p>
  </div>
  <div class="controls">
    <div class="seg bmseg" id="bmChip">
      <button title="★ 내 북마크만 보기">★ 내 북마크 <b id="bmCount">0</b></button>
    </div>
    <input id="q" placeholder="제목 · 주최 · 근거 검색">
    <select id="sort">
      <option value="dday">마감임박순</option>
      <option value="recent">최신순</option>
      <option value="fit">적합도순</option>
    </select>
    <div class="seg" id="viewSeg">
      <button data-v="card" class="on" title="카드 보기">카드</button>
      <button data-v="list" title="리스트 보기">리스트</button>
      <button data-v="time" title="마감 시점별 보기">타임라인</button>
    </div>
  </div>
  <div class="fl" id="policyFilters"></div>
  <div class="fl" id="modalityFilters"></div>
  <div class="fl" id="dateFilters"></div>
</header>
<main id="list"></main>
<script>
const DATA = __DATA__;
const POLICY = {
  must:{label:"AI 필수", icon:"✦"}, allowed:{label:"AI 허용", icon:"✓"},
  unclear:{label:"확인 필요", icon:"?"}, prohibited:{label:"AI 금지", icon:"⊘"},
  none:{label:"미분석", icon:"…"}
};
const MODALITY = {video:"영상", image:"이미지", text:"글", audio:"음악", software:"개발"};
const state = {policy:new Set(), modality:new Set(), period:"all", q:"", sort:"dday", view:"card", bmOnly:false};
const useServer = location.protocol === "http:" || location.protocol === "https:";
const BM_KEY = "contest_bookmarks";
const bookmarks = new Set(DATA.filter(it=>it.bookmarked).map(it=>it.ix));
function saveBookmarks(){ try{ localStorage.setItem(BM_KEY, JSON.stringify([...bookmarks])); }catch(e){} }
if(!useServer){ try{ JSON.parse(localStorage.getItem(BM_KEY)||"[]").forEach(ix=>bookmarks.add(ix)); }catch(e){} }
function isBm(ix){ return bookmarks.has(ix); }
function toggleBookmark(ix){
  const value = bookmarks.has(ix) ? 0 : 1;
  if(value) bookmarks.add(ix); else bookmarks.delete(ix);
  saveBookmarks();
  if(useServer){
    fetch("/api/bookmark",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({ix:ix,value:value})}).catch(()=>{});
  }
  render();
}

function policyOf(it){ return it.ai_policy || "none"; }
function parseDate(s){
  const m = s ? String(s).match(/(\d{4})-(\d{1,2})-(\d{1,2})/) : null;
  return m ? new Date(+m[1], +m[2]-1, +m[3]) : null;
}
function todayDate(){ const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); }
function ddayInfo(it){
  const end = parseDate(it.end_date);
  if(!end) return {text: it.dday || "", past: false, days: null};
  const days = Math.round((end - todayDate()) / 86400000);
  if(days < 0) return {text: "마감", past: true, days: days};
  if(days === 0) return {text: "오늘 마감", past: false, days: 0};
  return {text: "D-"+days, past: false, days: days};
}
function ddayNum(it){
  const info = ddayInfo(it);
  if(info.days === null) return 9998;
  if(info.past) return 9999 + Math.abs(info.days);
  return info.days;
}
function progressPct(it, info){
  if(info.past) return 100;
  const s = parseDate(it.start_date), e = parseDate(it.end_date);
  if(s && e && e > s){
    return Math.max(4, Math.min(100, Math.round((todayDate() - s) / (e - s) * 100)));
  }
  return info.days === null ? 0 : Math.max(4, 100 - info.days * 3.3);
}
function modalities(it){
  if(!it.ai_modality) return [];
  return String(it.ai_modality).split(",").map(s=>s.trim()).filter(Boolean);
}
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function sortRows(rows){
  const r = rows.slice();
  if(state.sort==="dday") r.sort((a,b)=>ddayNum(a)-ddayNum(b));
  else if(state.sort==="recent") r.sort((a,b)=>b.ix-a.ix);
  else if(state.sort==="fit") r.sort((a,b)=>(b.fit_score||0)-(a.fit_score||0));
  return r;
}
function filtered(){
  const q = state.q.toLowerCase();
  return sortRows(DATA.filter(it=>{
    if(state.bmOnly && !isBm(it.ix)) return false;
    if(state.policy.size && !state.policy.has(policyOf(it))) return false;
    if(state.modality.size && !modalities(it).some(m=>state.modality.has(m))) return false;
    const past = ddayInfo(it).past;
    if(state.period==="open" && past) return false;
    if(state.period==="closed" && !past) return false;
    if(q){
      const hay = [it.title,it.host,it.category,it.ai_evidence].join(" ").toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  }));
}
function chip(label,count,active,onclick){
  const el = document.createElement("span");
  el.className = "chip" + (active?" active":"");
  el.innerHTML = esc(label) + (count==null ? "" : '<span class="n">'+count+'</span>');
  el.onclick = onclick;
  return el;
}
function toggleSet(set, v){ if(set.has(v)) set.delete(v); else set.add(v); render(); }
function rowLabel(text){
  const s = document.createElement("span"); s.className = "lb"; s.textContent = text; return s;
}
function renderChips(){
  const pc = {}; DATA.forEach(it=>{ const p=policyOf(it); pc[p]=(pc[p]||0)+1; });
  const pf = document.getElementById("policyFilters"); pf.innerHTML="";
  pf.appendChild(rowLabel("판정"));
  pf.appendChild(chip("전체", DATA.length, state.policy.size===0, ()=>{ state.policy.clear(); render(); }));
  ["must","allowed","unclear","prohibited","none"].forEach(p=>{
    if(pc[p]) pf.appendChild(chip(POLICY[p].icon+" "+POLICY[p].label, pc[p], state.policy.has(p), ()=>toggleSet(state.policy,p)));
  });
  const mc = {}; DATA.forEach(it=>modalities(it).forEach(m=>mc[m]=(mc[m]||0)+1));
  const mf = document.getElementById("modalityFilters"); mf.innerHTML="";
  const keys = Object.keys(mc).sort();
  if(keys.length){
    mf.appendChild(rowLabel("형식"));
    mf.appendChild(chip("전체", DATA.length, state.modality.size===0, ()=>{ state.modality.clear(); render(); }));
    keys.forEach(m=>mf.appendChild(chip(MODALITY[m]||m, mc[m], state.modality.has(m), ()=>toggleSet(state.modality,m))));
  }
  const df = document.getElementById("dateFilters"); df.innerHTML="";
  const openCount = DATA.filter(it=>!ddayInfo(it).past).length;
  const closedCount = DATA.length - openCount;
  df.appendChild(rowLabel("기간"));
  df.appendChild(chip("기간 전체", DATA.length, state.period==="all", ()=>{ state.period="all"; render(); }));
  if(openCount) df.appendChild(chip("진행중·예정", openCount, state.period==="open", ()=>{ state.period="open"; render(); }));
  if(closedCount) df.appendChild(chip("마감", closedCount, state.period==="closed", ()=>{ state.period="closed"; render(); }));
}
function fieldRow(k, v, cls){
  if(!v) return "";
  return '<div class="row"><span class="k">'+k+'</span><span class="v '+(cls||'')+'">'+esc(v)+'</span></div>';
}
function badgeHtml(p){
  return '<span class="badge '+p+'">'+POLICY[p].icon+' '+esc(POLICY[p].label)+'</span>';
}
function prizeSummary(it){
  return it.prize_total_amount || it.prize_first_amount || it.prize_first || it.prize_total || "";
}
function card(it){
  const p = policyOf(it);
  const dd = ddayInfo(it);
  const hot = !dd.past && dd.days !== null && dd.days <= 3;
  const a = document.createElement("article");
  a.className = "card"+(isBm(it.ix)?" bm":"")+(dd.past?" expired":"")+(hot?" hot":"");
  const endText = it.end_date ? '<small>마감 '+esc(it.end_date)+'</small>' : "";
  const tags = modalities(it).map(m=>'<span class="tag">'+esc(MODALITY[m]||m)+'</span>').join("");
  const evidence = it.ai_evidence ? '<div class="evidence">'+esc(it.ai_evidence)+'</div>' : "";
  const homepage = it.homepage_url ? '<a href="'+esc(it.homepage_url)+'" target="_blank" rel="noopener">홈페이지</a>' : "";

  const fields = '<div class="fields">'+
    fieldRow("과제", it.sum_task)+
    fieldRow("주제", it.sum_topic || it.summary)+
    fieldRow("규격", it.sum_format)+
    fieldRow("대상", it.sum_target)+
    fieldRow("제출", it.sum_submit)+
    fieldRow("유의", it.sum_notes, "notes")+
  '</div>';

  const bd = it.prize_breakdown || [];
  let prizeBox = "";
  if(bd.length){
    const total = it.prize_total_amount ? ' <span style="font-weight:400">(총 '+esc(it.prize_total_amount)+')</span>' : "";
    const rows = bd.map((b,i)=>{
      const c = b.count ? b.count+"명" : "";
      return '<div class="prow"><span class="pr">'+esc((i+1)+". "+b.label)+'</span>'+
             '<span class="pc">'+esc(c)+'</span>'+
             '<span class="pm">'+esc(b.amount||"")+'</span></div>';
    }).join("");
    prizeBox = '<div class="prize-box"><div class="bd-title">시상내역'+total+'</div>'+rows+'</div>';
  } else {
    const amount = it.prize_first_amount || it.prize_first || "";
    if(amount){
      const label = (it.prize_first_label && it.prize_first_label!=="1등") ? it.prize_first_label : "1등";
      const c = it.prize_first_count ? it.prize_first_count+"명" : "";
      prizeBox = '<div class="prize-box"><div class="bd-title">시상내역</div>'+
        '<div class="prow"><span class="pr">'+esc(label)+'</span>'+
        '<span class="pc">'+esc(c)+'</span><span class="pm">'+esc(amount)+'</span></div></div>';
    } else if(it.prize_total){
      prizeBox = '<div class="prize-box"><div class="bd-title">시상내역</div>'+
        '<div class="prow"><span class="pr">'+esc(it.prize_total)+'</span></div></div>';
    }
  }

  a.innerHTML =
    '<div class="row1">'+badgeHtml(p)+
    '<span class="dday">'+esc(dd.text)+endText+'</span>'+
    '<button class="bm-btn'+(isBm(it.ix)?" on":"")+'" title="'+(isBm(it.ix)?"북마크 해제":"북마크 저장")+'">'+(isBm(it.ix)?"★":"☆")+'</button></div>'+
    '<div class="bar"><i style="width:'+progressPct(it,dd)+'%"></i></div>'+
    '<div><h3><a href="'+esc(it.detail_url)+'" target="_blank" rel="noopener">'+esc(it.title)+'</a></h3>'+
    '<div class="sub">'+esc(it.host||"")+' · '+esc(it.category||"")+'</div></div>'+
    fields+
    (tags ? '<div class="tags">'+tags+'</div>' : "")+
    prizeBox+
    evidence+
    '<div class="links">'+homepage+'<a href="'+esc(it.detail_url)+'" target="_blank" rel="noopener">위비티 원문</a></div>';
  const bmBtn = a.querySelector(".bm-btn");
  if(bmBtn) bmBtn.onclick = (e)=>{ e.preventDefault(); toggleBookmark(it.ix); };
  return a;
}
function listRow(it){
  const p = policyOf(it);
  const dd = ddayInfo(it);
  const hot = !dd.past && dd.days !== null && dd.days <= 3;
  const el = document.createElement("div");
  el.className = "lrow"+(dd.past?" expired":"")+(hot?" hot":"");
  el.innerHTML =
    '<span>'+badgeHtml(p)+'</span>'+
    '<span class="t"><a href="'+esc(it.detail_url)+'" target="_blank" rel="noopener">'+esc(it.title)+'</a></span>'+
    '<span class="dday">'+esc(dd.text)+'</span>'+
    '<span class="m">'+esc(prizeSummary(it))+'</span>'+
    '<button class="bm-btn'+(isBm(it.ix)?" on":"")+'">'+(isBm(it.ix)?"★":"☆")+'</button>';
  el.querySelector(".bm-btn").onclick = (e)=>{ e.preventDefault(); toggleBookmark(it.ix); };
  return el;
}
function cardGrid(rows){
  const g = document.createElement("div"); g.className = "grid";
  rows.forEach(it=>g.appendChild(card(it)));
  return g;
}
const TIME_GROUPS = [
  ["오늘·내일", d=>d!==null && d>=0 && d<=1],
  ["이번 주", d=>d!==null && d>=2 && d<=7],
  ["이번 달", d=>d!==null && d>=8 && d<=30],
  ["그 이후", d=>d!==null && d>30],
  ["마감 일자 미정", d=>d===null],
  ["마감", d=>d!==null && d<0]
];
function render(){
  renderChips();
  document.querySelectorAll("#viewSeg button").forEach(b=>b.classList.toggle("on", b.dataset.v===state.view));
  const bmBtn = document.querySelector("#bmChip button");
  bmBtn.classList.toggle("on", state.bmOnly);
  document.getElementById("bmCount").textContent = bookmarks.size;
  const rows = filtered();
  const list = document.getElementById("list"); list.innerHTML="";
  document.getElementById("total").textContent = DATA.length;
  document.getElementById("shown").textContent = rows.length;
  if(!rows.length){ list.innerHTML = '<div class="empty">조건에 맞는 공모전이 없습니다.</div>'; return; }
  if(state.view==="card"){
    list.appendChild(cardGrid(rows));
  } else if(state.view==="list"){
    rows.forEach(it=>list.appendChild(listRow(it)));
  } else {
    TIME_GROUPS.forEach(g=>{
      const sub = rows.filter(it=>g[1](ddayInfo(it).days));
      if(!sub.length) return;
      const h = document.createElement("div"); h.className = "gh"; h.textContent = g[0]+" ("+sub.length+")";
      list.appendChild(h);
      list.appendChild(cardGrid(sub));
    });
  }
}
document.getElementById("q").addEventListener("input", e=>{ state.q=e.target.value; render(); });
document.getElementById("bmChip").addEventListener("click", ()=>{ state.bmOnly = !state.bmOnly; render(); });
document.getElementById("sort").addEventListener("change", e=>{ state.sort=e.target.value; render(); });
document.getElementById("viewSeg").addEventListener("click", e=>{
  const b = e.target.closest("button"); if(!b) return;
  state.view = b.dataset.v; render();
});
render();
</script>
</body>
</html>
"""


_RANK_PRIORITY = {
    "그랑프리": 0, "대상": 1, "1등": 1, "1위": 1, "금상": 2, "최우수상": 2, "최우수": 3,
    "은상": 4, "우수상": 4, "2등": 4, "2위": 4, "동상": 6, "장려상": 6, "장려": 7,
    "3등": 7, "3위": 7, "특별상": 8, "입선": 9, "가작": 9,
}


def _rank_key(entry):
    label = entry.get("label") or ""
    for rank, priority in _RANK_PRIORITY.items():
        if rank in label:
            return priority
    return 99


def _parse_breakdown(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if isinstance(parsed, dict):
        parsed = parsed.get("breakdown", [])
    return parsed if isinstance(parsed, list) else []


def render(rows, generated_at):
    items = []
    for row in rows:
        items.append({
            "ix": row.get("ix"),
            "title": row.get("title"),
            "category": row.get("category"),
            "host": row.get("host"),
            "status": row.get("status"),
            "summary": row.get("summary"),
            "sum_task": row.get("sum_task"),
            "sum_topic": row.get("sum_topic"),
            "sum_format": row.get("sum_format"),
            "sum_target": row.get("sum_target"),
            "sum_submit": row.get("sum_submit"),
            "sum_notes": row.get("sum_notes"),
            "dday": row.get("dday"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "prize_total": row.get("prize_total"),
            "prize_total_amount": row.get("prize_total_amount"),
            "prize_first": row.get("prize_first"),
            "prize_first_label": row.get("prize_first_label"),
            "prize_first_count": row.get("prize_first_count"),
            "prize_first_amount": row.get("prize_first_amount"),
            "prize_breakdown": sorted(_parse_breakdown(row.get("prize_breakdown")), key=_rank_key),
            "homepage_url": row.get("homepage_url"),
            "detail_url": row.get("detail_url"),
            "ai_policy": row.get("ai_policy"),
            "ai_modality": row.get("ai_modality"),
            "ai_evidence": row.get("ai_evidence"),
            "confidence": row.get("confidence"),
            "fit_score": row.get("fit_score"),
            "bookmarked": bool(row.get("bookmarked")),
        })
    payload = json.dumps(items, ensure_ascii=False).replace("<", "\\u003c")
    return TEMPLATE.replace("__DATA__", payload).replace("__GENERATED__", generated_at)

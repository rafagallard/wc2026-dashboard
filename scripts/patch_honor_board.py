#!/usr/bin/env python3
"""Agrega Cuadro de Honor y filtro de histórico en predicciones.html."""

from pathlib import Path

HTML_PATH = Path("predicciones.html")


def add_once(text, marker, replacement):
    """Inserta contenido sólo si el marcador nuevo todavía no existe."""
    if marker in text:
        return text
    return replacement(text)


def main():
    """Aplica cambios idempotentes a la página de predicciones."""
    text = HTML_PATH.read_text(encoding="utf-8")

    # Agrega estilos compactos para el podio sin afectar las tablas existentes.
    if ".honor-grid" not in text:
        text = text.replace(
            ".winner-row{background:#dcfce7 !important}.winner-row td{font-weight:950;background:#dcfce7 !important}",
            ".winner-row{background:#dcfce7 !important}.winner-row td{font-weight:950;background:#dcfce7 !important}.honor-grid{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:14px}.honor-card{border:1px solid var(--line);border-radius:22px;background:linear-gradient(180deg,#fff,#f8fafc);padding:16px;box-shadow:0 8px 22px rgba(15,23,42,.07)}.honor-rank{font-size:28px}.honor-name{font-size:19px;font-weight:1000;margin-top:8px}.honor-count{font-size:13px;color:#166534;font-weight:950;margin-top:6px}.honor-last{font-size:12px;color:var(--muted);line-height:1.35;margin-top:8px}"
        )
        text = text.replace(
            "@media(max-width:1120px){.hero{grid-template-columns:1fr}.statusbar{justify-content:flex-start}.grid,.prediction-layout{grid-template-columns:1fr}",
            "@media(max-width:1120px){.hero{grid-template-columns:1fr}.statusbar{justify-content:flex-start}.grid,.prediction-layout,.honor-grid{grid-template-columns:1fr}"
        )

    # Agrega la sección visual del Cuadro de Honor antes de ganadores de la fecha.
    if 'id="honorBoard"' not in text:
        text = text.replace(
            '  <section><div class="section-title"><h2>Ganadores de la fecha</h2></div><section class="card"><div class="card-head"><h3>Aciertos exactos</h3><span id="winnerCount">0 ganador(es)</span></div><div class="card-body"><div id="winnersTable"></div></div></section></section>',
            '  <section><div class="section-title"><h2>Cuadro de Honor</h2><span id="honorBoardCount">Top 3 histórico</span></div><section class="card"><div class="card-head"><h3>Marcadores exactos</h3><span>Histórico completo</span></div><div class="card-body"><div id="honorBoard"></div></div></section></section>\n  <section><div class="section-title"><h2>Ganadores de la fecha</h2></div><section class="card"><div class="card-head"><h3>Aciertos exactos</h3><span id="winnerCount">0 ganador(es)</span></div><div class="card-body"><div id="winnersTable"></div></div></section></section>'
        )

    # Agrega selector para filtrar el histórico sin cambiar la fuente de datos.
    if 'id="historyFilter"' not in text:
        text = text.replace(
            '<div class="history-toolbar"><select id="historyDate"></select><button class="secondary" id="showSelectedHistory">Ver día seleccionado</button><button class="secondary" id="showAllHistory">Ver todo el histórico</button></div>',
            '<div class="history-toolbar"><select id="historyDate"></select><select id="historyFilter"><option value="all">Todas las predicciones</option><option value="won">Sólo ganadas</option><option value="lost">Sólo no ganadas</option></select><button class="secondary" id="showSelectedHistory">Ver día seleccionado</button><button class="secondary" id="showAllHistory">Ver todo el histórico</button></div>'
        )

    # Agrega funciones de ranking y filtro después de la tabla de ganadores.
    if "function honorBoardRows" not in text:
        insert_after = "function selectedRows(){return allPredictions.filter(r=>String(r.date)===String(selectedDate()))}"
        honor_js = """
function honorBoardRows(){
  const winners=exactWinnerRows(allPredictions),board={};
  winners.forEach(r=>{
    const key=normalizePersonName(r.person),name=String(r.person||'').trim();
    if(!key)return;
    if(!board[key])board[key]={name,count:0,lastDate:'',lastMatch:''};
    board[key].count+=1;
    const match=`${r.team1} vs ${r.team2}`;
    if(String(r.date)>String(board[key].lastDate||'')){board[key].lastDate=r.date;board[key].lastMatch=match}
  });
  return Object.values(board).sort((a,b)=>b.count-a.count||String(b.lastDate).localeCompare(String(a.lastDate))||a.name.localeCompare(b.name)).slice(0,3)
}
function renderHonorBoard(){
  const rows=honorBoardRows(),medals=['🥇','🥈','🥉'];
  $('honorBoardCount').textContent=`${rows.length} lugar(es)`;
  $('honorBoard').innerHTML=rows.length?`<div class="honor-grid">${rows.map((r,i)=>`<article class="honor-card"><div class="honor-rank">${medals[i]}</div><div class="honor-name">${esc(r.name)}</div><div class="honor-count">${r.count} acierto(s) exacto(s)</div><div class="honor-last">Último acierto: ${esc(r.lastMatch||'—')}<br>${esc(r.lastDate||'')}</div></article>`).join('')}</div>`:'<div class="empty">Todavía no hay aciertos exactos en el histórico.</div>'
}
function historyFilterRows(rows){
  const mode=$('historyFilter')?.value||'all';
  if(mode==='won')return rows.filter(isWinnerRow);
  if(mode==='lost')return rows.filter(r=>!isWinnerRow(r));
  return rows
}
"""
        text = text.replace(insert_after, honor_js + insert_after)

    # Conecta el widget y el filtro con el refresco existente.
    text = text.replace(
        "function renderSelectedPredictions(){const rows=selectedRows();$('todayPredictionCount').textContent=`${rows.length} registro(s)`;$('todayPredictions').innerHTML=rowsToTable(rows);$('winnersTable').innerHTML=winnersToTable(rows)}",
        "function renderSelectedPredictions(){const rows=selectedRows();$('todayPredictionCount').textContent=`${rows.length} registro(s)`;$('todayPredictions').innerHTML=rowsToTable(rows);$('winnersTable').innerHTML=winnersToTable(rows);renderHonorBoard()}"
    )
    text = text.replace(
        "function renderSelectedHistory(){const d=$('historyDate').value;$('historyTable').innerHTML=d?rowsToTable(allPredictions.filter(r=>String(r.date)===String(d))):'<div class=\"empty\">No hay días guardados todavía.</div>'}",
        "function renderSelectedHistory(){const d=$('historyDate').value;$('historyTable').innerHTML=d?rowsToTable(historyFilterRows(allPredictions.filter(r=>String(r.date)===String(d)))):'<div class=\"empty\">No hay días guardados todavía.</div>'}"
    )
    text = text.replace(
        "function renderAllHistory(){$('historyTable').innerHTML=rowsToTable(allPredictions)}",
        "function renderAllHistory(){$('historyTable').innerHTML=rowsToTable(historyFilterRows(allPredictions))}"
    )

    # Agrega listener del filtro si todavía no existe.
    if "historyFilter').addEventListener" not in text:
        text = text.replace(
            "$('showAllHistory').addEventListener('click',renderAllHistory);",
            "$('showAllHistory').addEventListener('click',renderAllHistory);\n$('historyFilter').addEventListener('change',renderSelectedHistory);"
        )

    HTML_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

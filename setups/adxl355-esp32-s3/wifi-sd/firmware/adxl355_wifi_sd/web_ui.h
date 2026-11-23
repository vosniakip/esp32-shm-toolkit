#pragma once
#include <Arduino.h>
const char WEB_UI[] PROGMEM=R"HTML(<!doctype html>
<html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ADXL355 | Ensaios</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1050px;margin:24px auto;padding:0 18px;color:#173047;background:#f5f8fa}
h1{font-size:25px}h2{font-size:20px}section{background:white;border:1px solid #d7e0e7;border-radius:10px;padding:18px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}label{display:flex;flex-direction:column;gap:4px}
input,select,textarea,button{font:inherit;padding:9px;border:1px solid #a9bac7;border-radius:5px}button{cursor:pointer;background:#0e5b82;color:white;margin:6px 4px 6px 0}button.stop{background:#982d31}
button:disabled{opacity:.5;cursor:default}pre{white-space:pre-wrap;word-break:break-word;font-size:13px;max-height:350px;overflow:auto}
.note{font-size:14px;color:#4c626e}#message{font-weight:600}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left;font-size:14px}a{color:#065e8a}
</style>
<h1>ADXL355 + ESP32-S3</h1><p>Aquisição local e controle dos ensaios.</p>
<section><div id="message">Consultando o nó...</div><pre id="status"></pre>
<button onclick="refresh()">Atualizar estado</button><button onclick="info()">Identificação</button>
<button class="stop" onclick="stopRun()">Parar / cancelar sequência</button></section>
<section><h2>Configurar aquisição</h2><form id="form"><div class="grid">
<label>Identificação do sensor<input name="sensor" value="adxl355-01" maxlength="24" required pattern="[A-Za-z0-9_-]+"></label>
<label>Montagem<input name="montagem" value="pcb-inclinada-v1" maxlength="32" required pattern="[A-Za-z0-9_-]+"></label>
<label>Ensaio<select name="ensaio"><option>funcional</option><option>calibracao</option><option>validacao</option><option>ruido</option><option>repetibilidade</option><option>remontagem</option><option>aquecimento</option><option>dinamico</option><option>allan</option><option>referencia</option><option>validacao_wifi</option></select></label>
<label>Posição<input name="posicao" value="zpos" maxlength="24" required pattern="[A-Za-z0-9_-]+"></label>
<label>Referencial da posição<select name="referencial"><option value="conjunto">Conjunto / base</option><option value="sensor">Sensor</option></select></label>
<label>Duração (s)<input type="number" name="duracao_s" value="30" min="1" max="21600" required></label>
<label>Taxa (Hz)<select name="taxa"><option>500</option><option>250</option></select></label>
<label>Faixa (±g)<select name="faixa"><option>2</option><option>4</option><option>8</option></select></label>
<label>Primeira repetição<input type="number" name="repeticao" value="1" min="1" max="999" required></label>
<label>Quantidade de registros<input type="number" name="repeticoes" value="1" min="1" max="20" required></label>
<label>Intervalo entre registros (s)<input type="number" name="intervalo_s" value="10" min="0" max="3600" required></label>
<label>Atraso inicial (s)<input type="number" name="atraso_s" value="5" min="0" max="3600" required></label>
<label>Wi-Fi durante o registro<select name="radio"><option value="ativo">Controle remoto ativo</option><option value="desligado">Desligado até terminar a sequência</option></select></label>
<label>Identificador da calibração<input name="calibracao_id" value="nao-aplicada" maxlength="40" pattern="[A-Za-z0-9_-]+"></label>
</div><label style="margin-top:12px">Observação<textarea name="nota" maxlength="240" rows="2"></textarea></label>
<p class="note">X/Y/Z da posição referem-se à base quando escolhido “conjunto”. A faixa e a taxa permanecem constantes na sequência. O nó continua gravando se esta página for fechada. Nenhum coeficiente é aplicado aos dados brutos.</p>
<button type="submit" id="start">Iniciar sequência</button>
<button type="button" onclick="armBoot()">Preparar uma partida a frio</button>
<button type="button" onclick="disarmBoot()">Desarmar partida a frio</button></form>
<p class="note">Partida a frio: salva estas opções para uma única execução após a próxima energização. Não reinicia o nó agora. Confirme INFO antes de desligar.</p></section>
<section><h2>Arquivos</h2><button onclick="files(0)">Listar aquisições</button><button id="next" hidden>Próxima página</button>
<p class="note">Downloads são liberados após o fim da sequência. Para conferir SHA-256 e converter para CSV/XLSX, use o programa Python incluído no pacote.</p>
<div id="files"></div></section>
<section><h2>Diagnóstico</h2><pre id="details"></pre></section>
<script>
const $=x=>document.getElementById(x);let current=null;
const token=()=>Date.now().toString(16)+'-'+Math.random().toString(16).slice(2,14);
const form=()=>new URLSearchParams(new FormData($('form')));
function message(s){$('message').textContent=s}
async function api(path,data){let r=await fetch(path,data?{method:'POST',body:data,cache:'no-store'}:{cache:'no-store'});let j=await r.json();if(!r.ok)throw Error(j.erro||r.statusText);return j}
async function refresh(){try{current=await api('/api/status');$('status').textContent=JSON.stringify(current,null,2);$('start').disabled=current.ocupado;message(current.ocupado?'Sequência em andamento.':'Nó disponível.');}catch(e){message('Sem resposta: '+e.message+'. Em modo rádio desligado, reconecte à rede após a duração programada.')}}
async function info(){try{$('details').textContent=JSON.stringify(await api('/api/info'),null,2)}catch(e){message(e.message)}}
async function clock(){return api('/api/clock',new URLSearchParams({epoch_ms:Date.now().toString()}))}
$('form').onsubmit=async e=>{e.preventDefault();let data=form();data.set('request_id',token());$('start').disabled=true;try{await clock();let j=await api('/api/start',data);$('details').textContent=JSON.stringify(j,null,2);message(data.get('radio')==='desligado'?'Comando aceito. A rede será desligada; reconecte ao final.':'Comando aceito.');}catch(err){message('Falha/resultado incerto: '+err.message+'. Consulte o estado antes de iniciar novamente.')}finally{setTimeout(refresh,800)}};
async function stopRun(){try{$('details').textContent=JSON.stringify(await api('/api/stop',new URLSearchParams({stop:'1'})),null,2);refresh()}catch(e){message(e.message)}}
async function armBoot(){try{let d=form();d.set('habilitar','1');$('details').textContent=JSON.stringify(await api('/api/autostart',d),null,2);message('Próxima partida armada. Desligue o conjunto somente quando estiver ocioso.')}catch(e){message(e.message)}}
async function disarmBoot(){try{$('details').textContent=JSON.stringify(await api('/api/autostart',new URLSearchParams({habilitar:'0'})),null,2)}catch(e){message(e.message)}}
async function files(offset){try{let j=await api('/api/files?offset='+offset);let t=document.createElement('table');let h=t.insertRow();for(let a of ['Aquisição','Estado','Downloads']){let th=document.createElement('th');th.textContent=a;h.appendChild(th)}for(let f of j.arquivos){let r=t.insertRow();r.insertCell().textContent=f.id;r.insertCell().textContent=f.finalizado?'Finalizado':'Parcial / verificar';let c=r.insertCell();for(let k of ['bin','meta','manifest','log']){let a=document.createElement('a');a.textContent=k+' ';a.href='/api/download?run='+encodeURIComponent(f.id)+'&kind='+k;c.appendChild(a)}}$('files').replaceChildren(t);$('next').hidden=!j.mais;$('next').onclick=()=>files(j.proximo_offset)}catch(e){message(e.message)}}
setInterval(refresh,2000);refresh();info();
</script></html>)HTML";

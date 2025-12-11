/** ConectAI-JVA - Frontend Optimizado (V3: Fix Restore & Feedback) */
const state={conversationId:null,isProcessing:false,user:null,showTrash:false,pendingAction:null};
const els={}; ['chatInput','sendBtn','messagesContainer','historyList','newChatBtn','themeToggleBtn','sidebar','sidebarOverlay','menuToggle','closeSidebarBtn','welcomeScreen','googleSignInBtn','userProfile','userName','userAvatar','logoutBtn','inputWrapper','sidebarToggleBtn','deleteModal','renameModal','renameInput','confirmDeleteBtn','cancelDeleteBtn','confirmRenameBtn','cancelRenameBtn'].forEach(id=>els[id]=document.getElementById(id));

// ============== CORE & AUTH ==============
    checkAuth(); setupEventListeners();
    document.documentElement.setAttribute('data-theme',localStorage.getItem('theme')||'light');
    if(window.marked){ const r=new marked.Renderer(); r.link=({href,title,text})=>`<a href="${href}" target="_blank" rel="noopener noreferrer" title="${title||''}">${text}</a>`; marked.use({renderer:r}); }
async function checkAuth(){
    try{ const r=await fetch('/api/auth/status'), d=await r.json(); if(d.logged_in) loginUser(d.user); else { localStorage.removeItem('jva_user'); renderGoogleButton(); } }catch(e){renderGoogleButton();}
}
function renderGoogleButton(){
    if(!els.googleSignInBtn)return; els.googleSignInBtn.style.display='flex'; if(els.userProfile)els.userProfile.style.display='none';
    if(window.google) fetch('/api/config').then(r=>r.json()).then(c=>{google.accounts.id.initialize({client_id:c.google_client_id,callback:hCR});google.accounts.id.renderButton(els.googleSignInBtn,{theme:'outline',size:'large',width:'100%'});}); else setTimeout(renderGoogleButton,500);
}
async function hCR(r){
    const res=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({credential:r.credential})}), d=await res.json();
    if(d.success) loginUser(d.user);
}
function loginUser(u){
    state.user=u; localStorage.setItem('jva_user',JSON.stringify(u));
    if(els.googleSignInBtn)els.googleSignInBtn.style.display='none'; if(els.userProfile)els.userProfile.style.display='flex';
    if(els.userName)els.userName.textContent=u.name||u.email; if(els.userAvatar)els.userAvatar.src=u.picture||''; loadChatHistory();
}
function logoutUser(){
    fetch('/api/auth/logout').then(()=>{state.user=null;state.conversationId=null;localStorage.removeItem('jva_user');location.reload();});
}

// ============== LOGICA DE CHAT ==============
async function sendMessage(){
    const txt=els.chatInput?.value.trim(); if(!txt||state.isProcessing||!state.user)return;
    state.isProcessing=true;
    if(els.welcomeScreen)els.welcomeScreen.style.display='none'; if(els.messagesContainer)els.messagesContainer.style.display='flex';
    if(els.chatInput)els.chatInput.value=''; if(els.sendBtn)els.sendBtn.disabled=true;
    addMessage('user',txt); scrollToBottom();
    
    // [FIX] Mostrar indicador de carga inmediato
    const loadingId = 'loading-' + Date.now();
    addMessage('assistant', '<i class="fas fa-spinner fa-spin"></i> Escribiendo...', null, null, loadingId);
    
    try{
        const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt,user_email:state.user.email,conversation_id:state.conversationId})});
        const d=await r.json();
        
        // Eliminar indicador de carga
        const loadMsg = document.querySelector(`[data-temp-id="${loadingId}"]`);
        if(loadMsg) loadMsg.remove();

        if(d.success){
            if(d.conversation_id)state.conversationId=d.conversation_id;
            addMessage('assistant',d.response,d.message_id,d.log_id);
            if(d.conversation_id&&!document.querySelector(`[onclick*="${d.conversation_id}"]`))loadChatHistory();
        }else addMessage('assistant','Error procesando solicitud.');
    }catch(e){
        const loadMsg = document.querySelector(`[data-temp-id="${loadingId}"]`);
        if(loadMsg) loadMsg.remove();
        addMessage('assistant','Error de conexión.');
    }
    finally { state.isProcessing=false; if(els.sendBtn)els.sendBtn.disabled=false; scrollToBottom(); }
}
function addMessage(role,content,msgId=null,logId=null,tempId=null){
    const d=document.createElement('div'); d.className=`message ${role}`;
    if(msgId)d.dataset.messageId=msgId; if(logId)d.dataset.logId=logId; if(tempId)d.dataset.tempId=tempId;
    const parsed=window.marked?marked.parse(content):content;
    const actions=role==='assistant'?
        `<div class="msg-actions-row">
            <button class="action-btn" onclick="copyText(this)" title="Copiar"><i class="fas fa-copy"></i></button>
            <button class="action-btn feedback-btn" onclick="openFeedback('${msgId||''}','like',this)"><i class="fas fa-thumbs-up"></i></button>
            <button class="action-btn feedback-btn" onclick="openFeedback('${msgId||''}','dislike',this)"><i class="fas fa-thumbs-down"></i></button>
            <button class="action-btn" onclick="regenerate('${msgId||''}')" title="Regenerar"><i class="fas fa-redo"></i></button>
         </div>`:
        `<div class="msg-actions-row"><button class="action-btn" onclick="editMessage(this)"><i class="fas fa-edit"></i></button></div>`;
    d.innerHTML=`<div class="message-content">${parsed}</div><div class="message-actions">${actions}</div>`;
    els.messagesContainer?.appendChild(d);
}

// ============== HISTORIAL (Fix Restore Name) ==============
async function loadChatHistory(){
    if(!state.user||!els.historyList)return;
    try{
        const r=await fetch(`/api/conversations?email=${state.user.email}`), d=await r.json(); if(!d.conversations)return;
        let active=[],trash=[]; d.conversations.forEach(c=>(c.title||'').includes('🗑️ [DEL]')?trash.push(c):active.push(c));
        const list=state.showTrash?trash:active;
        list.sort((a,b)=>{const ap=(a.title||'').includes('📌'),bp=(b.title||'').includes('📌');return (ap&&!bp)?-1:(!ap&&bp)?1:new Date(b.created_at)-new Date(a.created_at);});
        
        const grps={'📌 Fijado':[],'Hoy':[],'Ayer':[],'Esta semana':[],'Antiguos':[]};
        if(!state.showTrash){
            list.forEach(c=>{
                if((c.title||'').includes('📌'))return grps['📌 Fijado'].push(c);
                const diff=(new Date()-new Date(c.created_at))/(1000*60*60*24);
                if(diff<1)grps['Hoy'].push(c); else if(diff<2)grps['Ayer'].push(c); else if(diff<7)grps['Esta semana'].push(c); else grps['Antiguos'].push(c);
            });
        }else grps['Papelera']=list;

        let html=state.showTrash?`<div class="trash-header-banner" onclick="toggleTrash(false)"><i class="fas fa-arrow-left"></i> Volver a Chats</div>`:'';
        ['📌 Fijado','Hoy','Ayer','Esta semana','Antiguos','Papelera'].forEach(k=>{
            if(!grps[k]?.length)return;
            html+=`<div class="history-section-title">${k}</div>`+grps[k].map(c=>{
                let raw=c.title||'Nuevo Chat', disp=raw.replace(/📌|🗑️ \[DEL\]/g,'').trim(), isPin=raw.includes('📌');
                let btns=state.showTrash?
                    `<button class="icon-btn restore-btn" onclick="manageChat('${c.id}','restore')" title="Restaurar"><i class="fas fa-trash-restore"></i></button>
                     <button class="icon-btn delete-forever-btn" onclick="manageChat('${c.id}','hard_delete','${state.user.email}')" title="Eliminar"><i class="fas fa-times"></i></button>`:
                    `<button class="icon-btn pin-btn" onclick="togglePin('${c.id}','${raw}')" style="${isPin?'color:var(--brand-accent)':''}"><i class="fas fa-thumbtack"></i></button>
                     <button class="icon-btn edit-btn" onclick="openRenameModal('${c.id}','${disp}')"><i class="fas fa-edit"></i></button>
                     <button class="icon-btn trash-btn" onclick="openDeleteModal('${c.id}')"><i class="fas fa-trash"></i></button>`;
                return `<div class="history-item ${state.conversationId===c.id?'active':''}" onclick="loadConversation('${c.id}')"><div class="hist-content"><span>${disp}</span></div><div class="hist-actions">${btns}</div></div>`;
            }).join('');
        });
        if(!state.showTrash) html+=`<div class="trash-footer-link" onclick="toggleTrash(true)"><i class="fas fa-trash-alt"></i> Papelera (${trash.length})</div>`;
        els.historyList.innerHTML=html||'<div class="history-placeholder">Sin conversaciones</div>';
    }catch(e){console.error(e);}
}
function toggleTrash(s){state.showTrash=s;loadChatHistory();}
function togglePin(id,t){ event.stopPropagation(); updateChatTitle(id,t.includes('📌')?t.replace(/📌\s?/g,''):`📌 ${t}`,true); }
function openRenameModal(id,n){ event.stopPropagation(); state.pendingAction={id,type:'rename',currentName:n}; if(els.renameInput)els.renameInput.value=n; if(els.renameModal)els.renameModal.style.display='flex'; }
function openDeleteModal(id){ event.stopPropagation(); const el=document.querySelector(`div[onclick*="${id}"] .hist-content span`); state.pendingAction={id,type:'trash',currentName:el?el.innerText:'Chat'}; if(els.deleteModal)els.deleteModal.style.display='flex'; }

async function confirmRename(){ if(!state.pendingAction)return; await updateChatTitle(state.pendingAction.id,els.renameInput.value,true); els.renameModal.style.display='none'; }
async function confirmDelete(){ if(!state.pendingAction)return; await updateChatTitle(state.pendingAction.id,`🗑️ [DEL] ${state.pendingAction.currentName}`); if(state.conversationId===state.pendingAction.id)resetChat(); els.deleteModal.style.display='none'; }
async function updateChatTitle(id,nT,pP=false){ await fetch(`/api/conversations/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:nT})}); loadChatHistory(); }

// [FIX] Restore ahora extrae nombre original del DOM
async function manageChat(id,act,ext=null){
    event.stopPropagation();
    let body=null;
    if(act==='restore'){
        const el=document.querySelector(`div[onclick*="${id}"] .hist-content span`);
        const orig=el?el.innerText.replace(/🗑️ \[DEL\]|🗑️/g,'').trim():'Chat Restaurado';
        body=JSON.stringify({title:orig});
    }
    await fetch(`/api/conversations/${id}${act==='hard_delete'?`?email=${ext}`:''}`,{method:act==='hard_delete'?'DELETE':'PUT',headers:act==='restore'?{'Content-Type':'application/json'}:{},body});
    loadChatHistory();
}

async function loadConversation(id){
    state.conversationId=id; if(els.messagesContainer){els.messagesContainer.innerHTML='';els.messagesContainer.style.display='flex';} if(els.welcomeScreen)els.welcomeScreen.style.display='none';
    document.querySelectorAll('.history-item').forEach(i=>i.classList.remove('active')); document.querySelector(`div[onclick*="${id}"]`)?.classList.add('active');
    try{ const r=await fetch(`/api/conversations/${id}/messages`),d=await r.json(); d.messages?.forEach(m=>addMessage(m.role,m.content,m.id)); scrollToBottom(); }catch(e){}
}
function resetChat(){ state.conversationId=null; if(els.messagesContainer){els.messagesContainer.innerHTML='';els.messagesContainer.style.display='none';} if(els.welcomeScreen)els.welcomeScreen.style.display='block'; if(els.chatInput)els.chatInput.value=''; document.querySelectorAll('.history-item').forEach(i=>i.classList.remove('active')); }
function scrollToBottom(){if(els.messagesContainer)els.messagesContainer.scrollTop=els.messagesContainer.scrollHeight;}

// ============== EDICIÓN & REGENERAR ==============
function editMessage(btn){ const row=btn.closest('.message'); const txt=row.querySelector('.message-content').innerText; row.innerHTML=`<div class="edit-wrapper" style="width:100%"><textarea class="edit-textarea" style="width:100%;min-height:60px;margin-bottom:10px">${txt}</textarea><div class="edit-actions" style="display:flex;gap:10px"><button class="modal-btn confirm" onclick="saveEdit(this,'${txt}')">Guardar</button><button class="modal-btn cancel" onclick="cancelEdit(this,'${txt}')">Cancelar</button><button class="voice-btn-mini" onclick="toggleDictation(this.parentNode.previousSibling,this)" style="border:none;background:none;cursor:pointer"><i class="fas fa-microphone"></i></button></div></div>`; }
async function saveEdit(btn,orig){
    const row=btn.closest('.message'), txt=row.querySelector('textarea').value; if(txt===orig){cancelEdit(btn,orig);return;}
    const msgId=row.dataset.messageId; 
    row.innerHTML=`<div class="message-content"><i class="fas fa-spinner fa-spin"></i> Guardando...</div>`;
    try{
        const url=msgId?`/api/chat/message/${msgId}`:'/api/chat';
        await fetch(url,{method:msgId?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(msgId?{content:txt,original_content:orig}:{message:txt,conversation_id:state.conversationId,user_email:state.user.email})});
        if(msgId) regenerate(); else { row.outerHTML=''; addMessage('user',txt); }
    }catch(e){row.innerHTML=`<div class="message-content">${orig}</div>`;}
}
function cancelEdit(btn,orig){ btn.closest('.message').innerHTML=`<div class="message-content">${window.marked?marked.parse(orig):orig}</div><div class="message-actions"><div class="msg-actions-row"><button class="action-btn" onclick="editMessage(this)"><i class="fas fa-edit"></i></button></div></div>`; }

async function regenerate(msgId){
    if(state.isProcessing)return; state.isProcessing=true;
    const msgs=document.querySelectorAll('.message.assistant'); const last=msgs[msgs.length-1];
    if(last) last.innerHTML='<div class="message-content"><i class="fas fa-spinner fa-spin"></i> Regenerando...</div>';
    try{ const r=await fetch('/api/chat/regenerate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conversation_id:state.conversationId})}); const d=await r.json(); if(d.success){ if(last)last.remove(); addMessage('assistant',d.response,d.message_id); } }catch(e){}
    state.isProcessing=false; scrollToBottom();
}

// ============== FEEDBACK MEJORADO (Toggle + Modal Ambos) ==============
function openFeedback(id,type,btn){
    // Toggle Off
    if(btn.classList.contains('active')){
         submitFeedback(id,'none','');
         btn.classList.remove('active');
         // Reactivar hermano
         const sib=btn.parentElement.querySelector(`.feedback-btn:not([onclick*="${type}"])`);
         if(sib)sib.disabled=false;
         return;
    }
    // Abrir Modal para ambos casos (Like y Dislike) para permitir comentario
    showFeedbackModal(id,type,btn);
}

function showFeedbackModal(id,type,btn){
    const isLike = type==='like';
    const m=document.createElement('div'); m.className='modal-overlay';
    // [FIX] Guardamos referencia al botón original usando un ID único temporal o closure
    // IDs y textos dinámicos
    const title = isLike ? '¿Por qué te fue útil?' : '¿Por qué no fue útil?';
    m.innerHTML=`<div class="modal-content">
        <h3>${title}</h3>
        <textarea id="fbRe" placeholder="${isLike?'Ej: Respuesta precisa...':'Ej: Información incorrecta...'}"></textarea>
        <div class="modal-actions">
            <button class="voice-btn" onclick="toggleDictation(document.getElementById('fbRe'),this)"><i class="fas fa-microphone"></i></button>
            <button class="modal-btn cancel" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
            <button class="modal-btn confirm" id="confirmFbBtn">Enviar</button>
        </div>
    </div>`;
    document.body.appendChild(m);
    
    // Bindear evento click safe (sin inline JS complejo)
    document.getElementById('confirmFbBtn').onclick = async () => {
        const comment = document.getElementById('fbRe').value;
        await submitFeedback(id, type, comment);
        
        // Actualizar UI Botón
        btn.classList.add('active');
        // Desactivar hermano para evitar doble voto simultáneo
        const sib=btn.parentElement.querySelector(`.feedback-btn:not([onclick*="${type}"])`);
        if(sib) { sib.classList.remove('active'); /*sib.disabled=true;*/ } // Opcional disable
        
        m.remove();
    };
}

async function submitFeedback(id,t,r){ await fetch(`/api/chat/message/${id}/feedback`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feedback:t,reason:r})}); showToast('Gracias','success'); }

// ============== UTILIDADES & VOZ ==============
function setupVoiceInput(){ if(!('webkitSpeechRecognition'in window))return; const b=document.createElement('button'); b.className='icon-btn voice-btn'; b.innerHTML='<i class="fas fa-microphone"></i>'; b.onclick=()=>toggleDictation(els.chatInput,b); if(els.sendBtn)els.sendBtn.parentNode.insertBefore(b,els.sendBtn); }
let rec=null;
function toggleDictation(inp,btn){
    if(!('webkitSpeechRecognition'in window))return showToast('No soportado','error');
    if(rec){rec.stop();rec=null;updMic(btn,false);return;}
    rec=new webkitSpeechRecognition(); rec.lang='es-ES'; rec.onstart=()=>updMic(btn,true); rec.onend=()=>{updMic(btn,false);rec=null;};
    rec.onresult=e=>{const t=e.results[0][0].transcript;inp.value+=(inp.value?' ':'')+t;inp.dispatchEvent(new Event('input'));}; rec.start();
}
function updMic(b,a){ b.style.color=a?'red':''; b.querySelector('i').className=a?'fas fa-stop-circle':'fas fa-microphone'; }
function setupEventListeners(){
    els.menuToggle?.addEventListener('click',()=>{els.sidebar.classList.add('active');els.sidebarOverlay.classList.add('active');});
    els.closeSidebarBtn?.addEventListener('click',()=>{els.sidebar.classList.remove('active');els.sidebarOverlay.classList.remove('active');});
    els.sidebarOverlay?.addEventListener('click',()=>{els.sidebar.classList.remove('active');els.sidebarOverlay.classList.remove('active');});
    els.sidebarToggleBtn?.addEventListener('click',()=>{const c=document.querySelector('.app-container');c.setAttribute('data-sidebar-collapsed',c.getAttribute('data-sidebar-collapsed')==='true'?'false':'true');});
    els.newChatBtn?.addEventListener('click',resetChat); els.sendBtn?.addEventListener('click',sendMessage); els.logoutBtn?.addEventListener('click',logoutUser);
    els.chatInput?.addEventListener('input', (e) => { if(els.sendBtn) els.sendBtn.disabled = !e.target.value.trim(); });
    els.chatInput?.addEventListener('keypress', (e) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    els.confirmRenameBtn?.addEventListener('click',confirmRename); els.cancelRenameBtn?.addEventListener('click',()=>{els.renameModal.style.display='none';});
    els.confirmDeleteBtn?.addEventListener('click',confirmDelete); els.cancelDeleteBtn?.addEventListener('click',()=>{els.deleteModal.style.display='none';});
    els.themeToggleBtn?.addEventListener('click',()=>{document.documentElement.setAttribute('data-theme',document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark');});
    document.querySelectorAll('.suggestion-card').forEach(c=>c.addEventListener('click',()=>{if(els.chatInput)els.chatInput.value=c.dataset.query;sendMessage();}));
    setupVoiceInput();
}
function showToast(m,t='info'){const el=document.getElementById('toast');if(el){el.querySelector('span').textContent=m;el.className=`toast ${t} show`;setTimeout(()=>el.classList.remove('show'),3000);}}
function copyText(b){navigator.clipboard.writeText(b.closest('.message').textContent).then(()=>showToast('Copiado'));}

document.addEventListener("DOMContentLoaded", () => {
  const $ = id => document.getElementById(id);
  const h = (tag, props = {}, ...children) => {
    const el = document.createElement(tag);
    Object.entries(props).forEach(([k, v]) => k.startsWith("on") ? el.addEventListener(k.substring(2).toLowerCase(), v) : k === "style" ? Object.assign(el.style, v) : k === "dataset" ? Object.assign(el.dataset, v) : k === "innerHTML" ? el.innerHTML = v : el[k] = v);
    children.flat().forEach(c => c && el.append(c)); return el;
  };

  const state = { isMinimized: false, isHidden: false, unread: 0, isProcessing: false, history: [], auth: false, abortCtrl: null, lastUserMsg: "" };
  const CFG = { BACKEND: "", MIN_W: 300, MIN_H: 400, MAX_W: 800, MAX_H: 700 };
  const els = { container: $("chatbotContainer"), header: $("chatbotHeader"), msgs: $("chatbotMessages"), input: $("chatbotInput"), sendBtn: $("chatbotSend"), badge: $("newMessageBadge"), notif: $("notification") };

  const interact = {
    mode: null, startData: {}, moved: false,
    init() {
      ["top-left","top-right","bottom-left","bottom-right","left","right","top","bottom"].forEach(p => els.container.appendChild(h("div", {className:`chatbot-resizer resizer-${p}`, dataset:{pos:p}})));
      const bind = (evt, fn, passive=true) => (evt.startsWith("touch")?els.container:document).addEventListener(evt, fn.bind(this), {passive});
      els.container.addEventListener("mousedown", this.start.bind(this)); document.addEventListener("mousemove", this.move.bind(this)); document.addEventListener("mouseup", this.end.bind(this));
      els.container.addEventListener("touchstart", this.start.bind(this), {passive: false}); document.addEventListener("touchmove", this.move.bind(this), {passive: false}); document.addEventListener("touchend", this.end.bind(this));
    },
    start(e) {
      if (state.isMinimized) this.mode = "drag";
      const target = e.target, isTouch = e.type === "touchstart";
      const resizer = target.closest(".chatbot-resizer"), header = target.closest(".chatbot-header");
      if (resizer && !state.isMinimized) { this.mode = "resize"; this.resizer = resizer.dataset.pos; }
      else if (header || state.isMinimized) { this.mode = "drag"; } else return;
      if (!isTouch || this.mode) e.preventDefault();
      const clientX = isTouch ? e.touches[0].clientX : e.clientX, clientY = isTouch ? e.touches[0].clientY : e.clientY;
      const rect = els.container.getBoundingClientRect();
      this.startData = { x: clientX, y: clientY, w: rect.width, h: rect.height, l: rect.left, t: rect.top };
      this.moved = false; els.container.classList.add("resizing"); els.container.style.transition = "none";
      // Pin position immediately to avoid jumps when removing transform
      Object.assign(els.container.style, { left: `${rect.left}px`, top: `${rect.top}px`, right: "auto", bottom: "auto", transform: "none" });
    },
    move(e) {
      if (!this.mode) return;
      const isTouch = e.type === "touchmove";
      const clientX = isTouch ? e.touches[0].clientX : e.clientX, clientY = isTouch ? e.touches[0].clientY : e.clientY;
      const dx = clientX - this.startData.x, dy = clientY - this.startData.y;
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) this.moved = true;
      if (isTouch) e.preventDefault();
      if (this.mode === "drag") {
        Object.assign(els.container.style, { left: `${Math.max(0, Math.min(this.startData.l + dx, window.innerWidth - this.startData.w))}px`, top: `${Math.max(0, Math.min(this.startData.t + dy, window.innerHeight - this.startData.h))}px`, right: "auto", bottom: "auto" });
      } else if (this.mode === "resize") {
        let { w, h, l, t } = this.startData;
        if (this.resizer.includes("right")) w = Math.min(CFG.MAX_W, Math.max(CFG.MIN_W, w + dx));
        if (this.resizer.includes("left")) { const nw = Math.min(CFG.MAX_W, Math.max(CFG.MIN_W, w - dx)); if (nw !== w) { l += w - nw; w = nw; } }
        if (this.resizer.includes("bottom")) h = Math.min(CFG.MAX_H, Math.max(CFG.MIN_H, h + dy));
        if (this.resizer.includes("top")) { const nh = Math.min(CFG.MAX_H, Math.max(CFG.MIN_H, h - dy)); if (nh !== h) { t += h - nh; h = nh; } }
        Object.assign(els.container.style, { width: `${w}px`, height: `${h}px`, left: `${l}px`, top: `${t}px` });
      }
    },
    end() {
      if (this.mode === "drag" && state.isMinimized && !this.moved) restoreChatbot();
      this.mode = null; els.container.classList.remove("resizing"); els.container.style.transition = "";
    }
  };

  const showNotif = (t, m, type="info") => {
    const n = els.notif; $("notificationTitle").textContent = t; $("notificationMessage").textContent = m;
    n.querySelector("i").className = `fas fa-${type==="success"?"check-circle":type==="error"?"exclamation-circle":"info-circle"}`;
    n.className = `notification ${type} show`; setTimeout(() => n.classList.remove("show"), 4000);
  };

  const restoreChatbot = () => {
    els.container.classList.remove("minimized", "hidden"); state.isMinimized = false; state.unread = 0; els.badge.style.display = "none";
  };

  const renderMessage = (msg, isUser, id = Date.now().toString(), rowNum = 0) => {
    let msgDiv = els.msgs.querySelector(`.message[data-id="${id}"]`);
    if (!msgDiv) {
      msgDiv = h("div", { className: `message ${isUser ? "user" : "bot"}`, dataset: { id, rowNumber: rowNum } });
      els.msgs.appendChild(msgDiv);
      if (!isUser) { state.history.push({ id, role: "assistant", content: msg }); } else { state.lastUserMsg = msg; state.history.push({ id, role: "user", content: msg }); }
    } else {
      msgDiv.innerHTML = "";
      if (!isUser) { const hItem = state.history.find(x => x.id === id); if (hItem) hItem.content = msg; }
    }
    const contentHtml = msg.split("\n").filter(t=>t.trim()).map(t => `<div>${t}</div>`).join("");
    msgDiv.append(h("div", { className: "message-bubble", innerHTML: contentHtml }));
    
    // Actions & Utils
    if (!isUser && !msg.includes("Autorizar Google")) {
      msgDiv.append(h("button", { className: "copy-message-btn", title: "Copiar", onclick: (e) => { e.stopPropagation(); copyToClipboard(msg); }, innerHTML: '<i class="fas fa-copy"></i>' }));
      const btns = [
        { cls: "like-btn", icon: "thumbs-up", title: "Útil", click: (e) => handleFeedback(id, true, e.currentTarget) },
        { cls: "dislike-btn", icon: "thumbs-down", title: "No útil", click: (e) => handleFeedback(id, false, e.currentTarget) },
        { cls: "regenerate-btn", icon: "redo", title: "Regenerar", click: () => processMessage(state.lastUserMsg) }
      ];
      msgDiv.append(h("div", { className: "message-actions" }, ...btns.map(b => h("button", { className: `action-btn ${b.cls}`, title: b.title, onclick: b.click, innerHTML: `<i class="fas fa-${b.icon}"></i>` }))));
    } else if (isUser) {
      msgDiv.append(h("button", { className: "copy-message-btn", title: "Editar", onclick: (e) => { e.stopPropagation(); startEdit(id, msg, rowNum); }, innerHTML: '<i class="fas fa-pen"></i>' }));
    }
    msgDiv.append(h("div", { className: "timestamp", textContent: new Date().toLocaleTimeString("es-PE", {hour:"2-digit",minute:"2-digit"})}));
    els.msgs.scrollTop = els.msgs.scrollHeight;
    if (state.isMinimized && !isUser) { state.unread++; els.badge.textContent = state.unread > 9 ? "9+" : state.unread; els.badge.style.display = "flex"; }
    return id;
  };

  const addLinkMessage = (text, linkTxt, url) => {
    const id = renderMessage(text, false);
    const bubble = els.msgs.querySelector(`.message[data-id="${id}"] .message-bubble`);
    bubble.append(h("div", { style: { marginTop: "10px" } }, h("a", { href: url, target: "_blank", textContent: linkTxt, style: { color: "#1c2682", fontWeight: "bold", textDecoration: "underline" } })));
  };

  const processMessage = async (msg) => {
    if (state.isProcessing) return;
    state.isProcessing = true;
    const isEdit = !!els.input.dataset.editId, editId = els.input.dataset.editId, rowNum = parseInt(els.input.dataset.editRow || 0);
    delete els.input.dataset.editId; delete els.input.dataset.editRow;
    const currentMsgId = isEdit ? renderMessage(msg, true, editId, rowNum) : renderMessage(msg, true);
    
    showTyping(); updateSendBtn(true);
    try {
      state.abortCtrl = new AbortController();
      const res = await fetch(`${CFG.BACKEND}/api/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, history: state.history, is_edit: isEdit, edit_id: editId, row_number: rowNum }),
        signal: state.abortCtrl.signal
      });
      const data = await res.json();
      if (res.ok) {
        if (data.auth_url) addLinkMessage(data.response, "Autorizar Google", data.auth_url);
        else renderMessage(data.response, false, data.id, data.row_number);
      } else renderMessage(`Error: ${data.error || "Desconocido"}`, false);
    } catch (e) {
      if (e.name === "AbortError") {
        els.input.value = msg; els.input.focus();
        const m = els.msgs.querySelector(`.message[data-id="${currentMsgId}"]`); if (m) m.remove();
        state.history = state.history.filter(h => h.id !== currentMsgId);
      } else renderMessage("Error de conexión.", false);
    } finally { hideTyping(); state.isProcessing = false; state.abortCtrl = null; updateSendBtn(false); }
  };

  const showTyping = () => { if (!$("typingIndicator")) els.msgs.append(h("div", { id: "typingIndicator", className: "typing-indicator" }, h("span"), h("span"), h("span"))); els.msgs.scrollTop = els.msgs.scrollHeight; };
  const hideTyping = () => $("typingIndicator")?.remove();
  const updateSendBtn = (stop) => { els.sendBtn.innerHTML = stop ? '<i class="fas fa-stop"></i>' : '<i class="fas fa-paper-plane"></i>'; els.sendBtn.title = stop ? "Detener" : "Enviar"; els.sendBtn.classList.toggle("stop", stop); };
  
  const startEdit = (id, text, rowNum) => {
    els.input.value = text; els.input.focus(); Object.assign(els.input.dataset, { editId: id, editRow: rowNum });
    const msgDiv = els.msgs.querySelector(`.message[data-id="${id}"]`);
    if (msgDiv) {
      const next = msgDiv.nextElementSibling;
      if (next && next.classList.contains("bot")) { state.history = state.history.filter(h => h.id !== next.dataset.id); next.remove(); }
      msgDiv.remove(); state.history = state.history.filter(h => h.id !== id);
    }
  };

  const copyToClipboard = async (text) => {
    try { await navigator.clipboard.writeText(text); showNotif("Copiado", "Texto copiado", "success"); }
    catch { const ta = h("textarea", { value: text, style: { position: "fixed", left: "-9999px" } }); document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove(); showNotif("Copiado", "Texto copiado", "success"); }
  };

  const handleFeedback = async (id, isLike, btn) => {
    const type = isLike ? "like" : "dislike", isActive = btn.classList.contains("active");
    if (isActive) { btn.classList.remove("active"); await sendFeedback(id, "none", "", btn); } 
    else {
      const sib = isLike ? btn.nextElementSibling : btn.previousElementSibling; if (sib) sib.classList.remove("active");
      btn.classList.add("active");
      const comment = !isLike ? prompt("¿Por qué no fue útil? (Opcional)") || "" : "";
      await sendFeedback(id, type, comment, btn);
    }
  };

  const sendFeedback = async (id, type, comment, btn) => {
    try {
      const msgDiv = els.msgs.querySelector(`.message[data-id="${id}"]`), rowNumber = msgDiv ? parseInt(msgDiv.dataset.rowNumber || 0) : 0;
      await fetch(`${CFG.BACKEND}/api/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message_id: id, feedback_type: type, comment, row_number: rowNumber }) });
    } catch { showNotif("Error", "No se pudo registrar tu opinión", "error"); btn.classList.remove("active"); }
  };

  const removeAuthMessages = () => {
    els.msgs.querySelectorAll(".message.bot").forEach(msg => {
      const txt = msg.textContent.toLowerCase();
      if (["conectar con google", "autorizar google", "conecta tu cuenta", "autorización"].some(k => txt.includes(k))) msg.remove();
    });
  };

  const checkAuthAndShowMessage = async () => {
    try {
      const { authenticated } = await fetch(`${CFG.BACKEND}/api/auth/status`).then(r => r.json());
      state.auth = authenticated;
      if (!state.auth) {
        if (!Array.from(els.msgs.querySelectorAll(".message.bot")).some(m => m.textContent.toLowerCase().includes("conectar con google"))) {
          const { auth_url } = await fetch(`${CFG.BACKEND}/api/auth/url`).then(r => r.json());
          if (auth_url) addLinkMessage("Para usar el asistente, primero conecta tu cuenta:", "Conectar con Google", auth_url);
        }
      } else { removeAuthMessages(); }
    } catch (e) { console.error("Auth check failed:", e); }
  };

  // Listeners
  $("minimizeChatbot").onclick = (e) => { e.stopPropagation(); state.isMinimized = !state.isMinimized; els.container.classList.toggle("minimized", state.isMinimized); if(state.isMinimized) els.container.style.height = ""; };
  $("closeChatbot").onclick = (e) => { e.stopPropagation(); els.container.classList.add("hidden"); state.isHidden = true; };
  els.sendBtn.onclick = (e) => { if (state.isProcessing) { e.preventDefault(); state.abortCtrl?.abort(); } else { const msg = els.input.value.trim(); if(msg) { processMessage(msg); els.input.value = ""; } } };
  els.input.onkeypress = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); els.sendBtn.click(); } };
  document.querySelectorAll(".suggestion-chip").forEach(chip => chip.onclick = () => { els.input.value = chip.dataset.message; els.sendBtn.click(); });
  
  window.addEventListener("message", (e) => {
    if (e.data === "oauth_success") {
      showNotif("Conectado", "Google autorizado correctamente", "success");
      removeAuthMessages(); setTimeout(() => window.location.reload(), 1500);
    }
  });

  interact.init();
  checkAuthAndShowMessage();
});

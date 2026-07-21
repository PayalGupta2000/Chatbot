(function () {
const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("msg");
const sendButton = document.getElementById("send-button");
const historyList = document.getElementById("history");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const storageKey = "chatbot.conversations.v1";
const docsKey = "chatbot.documents.v1";
const langKey = "chatbot.language.v1";
const maxConversations = 12;
let isSending = false;
let conversations = loadConversations();
let activeConversationId = conversations[0]?.id || createConversation();
let documents = loadDocuments();
let targetLanguage = loadLanguage();

function setStatus(state, msg) {
	statusDot.className = "status-dot" + (state === "busy" ? " busy" : state === "error" ? " error" : "");
	statusText.textContent = msg;
}

function scrollToBottom() {
	chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: "smooth" });
}

function removeWelcome() {
	document.getElementById("welcome")?.remove();
}

function createConversation() {
	if (conversations.length >= maxConversations) conversations.pop();
	const conversation = {
		id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
		title: "New conversation",
		updatedAt: Date.now(),
		messages: [],
	};
	conversations.unshift(conversation);
	persistConversations();
	return conversation.id;
}

function loadConversations() {
	try {
		const stored = JSON.parse(window.localStorage.getItem(storageKey));
		return Array.isArray(stored) ? stored.filter(isValidConversation).slice(0, maxConversations) : [];
	} catch {
		return [];
	}
}

function isValidConversation(conversation) {
	return conversation && typeof conversation.id === "string" && typeof conversation.title === "string" && Array.isArray(conversation.messages);
}

function persistConversations() {
	try {
		window.localStorage.setItem(storageKey, JSON.stringify(conversations.slice(0, maxConversations)));
	} catch (error) {
		console.warn("Unable to save chat history:", error);
	}
}

function activeConversation() {
	return conversations.find((c) => c.id === activeConversationId);
}

function addToConversation(role, content, action) {
	const conversation = activeConversation();
	if (!conversation) return;
	conversation.messages.push({ role, content, action });
	if (role === "user" && conversation.messages.length === 1) {
		conversation.title = content.replace(/\s+/g, " ").slice(0, 42) || "New conversation";
	}
	conversation.updatedAt = Date.now();
	conversations.sort((a, b) => b.updatedAt - a.updatedAt);
	persistConversations();
	renderHistory();
}

function escapeHtml(value) {
	const el = document.createElement("div");
	el.textContent = value;
	return el.innerHTML;
}

function formatAssistantReply(reply) {
	const escaped = escapeHtml(String(reply)).replace(/\r\n/g, "\n");
	const codeBlocks = [];
	const withoutCodeBlocks = escaped.replace(/```([^`]*)```/g, (_, code) => {
		codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`);
		return `@@CODE_${codeBlocks.length - 1}@@`;
	});
	const inline = (text) => text.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>");
	const lines = withoutCodeBlocks.split("\n");
	const output = [];
	let listType = null;
	let sectionOpen = false;
	const closeList = () => { if (listType) output.push(`</${listType}>`); listType = null; };
	const closeSection = () => { closeList(); if (sectionOpen) output.push("</section>"); sectionOpen = false; };
	lines.forEach((line, index) => {
		const heading = line.match(/^(#{1,3})\s+(.+)$/);
		const bullet = line.match(/^\s*[-*]\s+(.+)$/);
		const numbered = line.match(/^\s*\d+\.\s+(.+)$/);
		const nextLine = lines.slice(index + 1).find((item) => item.trim());
		const sectionTitle = line.match(/^(.{3,90}):\s*$/);
		const isSectionTitle = sectionTitle && /^\s*(?:[-*]|\d+\.)\s+/.test(nextLine || "");
		if (heading) { closeSection(); output.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); }
		else if (isSectionTitle) { closeSection(); sectionOpen = true; output.push(`<section class="reply-section"><h3>${inline(sectionTitle[1])}</h3>`); }
		else if (bullet || numbered) { const nt = bullet ? "ul" : "ol"; if (listType && listType !== nt) closeList(); if (!listType) { output.push(`<${nt}>`); listType = nt; } output.push(`<li>${inline((bullet || numbered)[1])}</li>`); }
		else if (line.startsWith("&gt; ")) { closeList(); output.push(`<blockquote>${inline(line.slice(5))}</blockquote>`); }
		else if (line.startsWith("@@CODE_")) { closeList(); output.push(line); }
		else if (line.trim()) { closeList(); output.push(`<p>${inline(line)}</p>`); }
		else { closeList(); }
	});
	closeSection();
	return output.join("").replace(/@@CODE_(\d+)@@/g, (_, index) => codeBlocks[index]);
}

function createActionCard(action) {
	if (!action) return "";
	const card = document.createElement("div");
	card.className = "action-card";
	if (action.type === "data_imported") {
		card.innerHTML = `<div class="action-card-icon">📊</div><div class="action-card-body"><strong>Data Import Complete</strong><div class="action-card-details"><span class="badge success">${action.success||0} imported</span>${action.failed ? `<span class="badge error">${action.failed} failed</span>` : ""}<span>DocType: ${escapeHtml(action.doctype)}</span></div></div>`;
	} else if (action.type === "api_created") {
		card.innerHTML = `<div class="action-card-icon">🔌</div><div class="action-card-body"><strong>API Endpoint Created</strong><div class="action-card-details"><code>${escapeHtml(action.endpoint_url)}</code></div></div>`;
	} else if (action.type === "client_script_created" || action.type === "client_script_updated") {
		card.innerHTML = `<div class="action-card-icon">📜</div><div class="action-card-body"><strong>${action.type === "client_script_created" ? "Client Script Created" : "Client Script Updated"}</strong><div class="action-card-details"><span>${escapeHtml(action.name)}</span><span>DocType: ${escapeHtml(action.doctype)}</span></div></div>`;
	} else if (action.type === "api_updated") {
		card.innerHTML = `<div class="action-card-icon">🔌</div><div class="action-card-body"><strong>API Endpoint Updated</strong><div class="action-card-details"><code>${escapeHtml(action.endpoint_url)}</code></div></div>`;
	}
	return card;
}

function createMessage(content, role, isTyping = false) {
	removeWelcome();
	const row = document.createElement("div");
	row.className = `message-row ${role}`;
	const avatar = document.createElement("div");
	avatar.className = "avatar";
	avatar.textContent = role === "user" ? "You" : "AI";
	const bubble = document.createElement("div");
	bubble.className = "msg";
	if (isTyping) {
		bubble.classList.add("typing");
		bubble.innerHTML = "<span></span><span></span><span></span>";
	} else {
		bubble.textContent = content;
	}
	const contentWrap = document.createElement("div");
	contentWrap.appendChild(bubble);
	row.append(avatar, contentWrap);
	chatBox.appendChild(row);
	scrollToBottom();
	return { row, bubble, contentWrap };
}

function addCopyButton(contentWrap, text, label) {
	const actions = document.createElement("div");
	actions.className = "message-actions";
	const button = document.createElement("button");
	button.type = "button";
	button.className = "copy-btn";
	button.textContent = label || "Copy";
	button.addEventListener("click", async () => {
		try {
			await navigator.clipboard.writeText(text);
			button.textContent = "Copied!";
			setTimeout(() => { button.textContent = label || "Copy"; }, 1500);
		} catch {
			button.textContent = "Unavailable";
		}
	});
	actions.appendChild(button);
	contentWrap.appendChild(actions);
}

function addTranslateButton(contentWrap, text, role) {
	const actions = document.createElement("div");
	actions.className = "message-actions";
	const langs = ["Spanish", "French", "German", "Japanese", "Hindi", "Arabic"];
	const select = document.createElement("select");
	select.className = "translate-select";
	select.innerHTML = `<option value="">Translate</option>${langs.map((l) => `<option value="${l}">${l}</option>`).join("")}`;
	select.addEventListener("change", async () => {
		const lang = select.value;
		if (!lang) return;
		select.disabled = true;
		select.style.opacity = ".5";
		try {
			const resp = await fetch("/api/method/chatbot.ai_agent.chat", {
				method: "POST",
				headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
				body: JSON.stringify({ message: `Translate the following ${role} message to ${lang}. Respond with ONLY the translated text, nothing else:\n\n${text}` }),
			});
			const data = await resp.json();
			if (!resp.ok) throw new Error(data?.exc);
			const translation = data?.message?.reply || text;
			showToast(`Translated to ${lang}`);
			const row = contentWrap.closest(".message-row");
			const bubble = row?.querySelector(".msg");
			if (bubble) bubble[role === "ai" ? "innerHTML" : "textContent"] = role === "ai" ? formatAssistantReply(translation) : translation;
		} catch {
			showToast("Translation failed");
		} finally {
			select.disabled = false;
			select.style.opacity = "";
			select.value = "";
		}
	});
	actions.appendChild(select);
	contentWrap.appendChild(actions);
}

function addEditButton(contentWrap, index, content) {
	const actions = document.createElement("div");
	actions.className = "message-actions";
	const button = document.createElement("button");
	button.type = "button";
	button.className = "edit-btn";
	button.textContent = "Edit";
	button.addEventListener("click", () => {
		const conversation = activeConversation();
		if (!conversation) return;
		conversation.messages.splice(index);
		persistConversations();
		renderConversation();
		messageInput.value = content;
		resizeInput();
		messageInput.focus();
	});
	actions.appendChild(button);
	contentWrap.appendChild(actions);
}

function addRetryButton(contentWrap, message, conversationId) {
	const actions = document.createElement("div");
	actions.className = "message-actions";
	const button = document.createElement("button");
	button.type = "button";
	button.className = "copy-btn";
	button.textContent = "Try again";
	button.addEventListener("click", () => {
		const conversation = conversations.find((item) => item.id === conversationId);
		const lastMessage = conversation?.messages[conversation.messages.length - 1];
		if (lastMessage?.role === "user" && lastMessage.content === message) {
			conversation.messages.pop();
			persistConversations();
		}
		activeConversationId = conversationId;
		contentWrap.closest(".message-row")?.remove();
		sendMsg(message);
	});
	actions.appendChild(button);
	contentWrap.appendChild(actions);
}

function setComposerState(sending) {
	isSending = sending;
	sendButton.disabled = sending;
	sendButton.textContent = sending ? "…" : "↑";
	setStatus(sending ? "busy" : "ready", sending ? "Thinking…" : "Ready");
}

function loadLanguage() {
	try { return window.localStorage.getItem(langKey) || ""; } catch { return ""; }
}

function persistLanguage(lang) {
	try { window.localStorage.setItem(langKey, lang); } catch {}
}

function loadDocuments() {
	try { const s = JSON.parse(window.localStorage.getItem(docsKey)); return Array.isArray(s) ? s : []; } catch { return []; }
}

function persistDocuments() {
	try { window.localStorage.setItem(docsKey, JSON.stringify(documents)); } catch (error) { console.warn("Unable to save documents:", error); }
}

function getDocIcon(type) {
	if (/pdf/i.test(type)) return "📄";
	if (/docx?/i.test(type)) return "📝";
	if (/xlsx?/i.test(type)) return "📊";
	if (/csv/i.test(type)) return "📋";
	if (/pptx?/i.test(type)) return "📽";
	if (/png|jpg|jpeg|gif|bmp|webp/i.test(type)) return "🖼";
	return "📁";
}

function isImageType(type) { return /png|jpg|jpeg|gif|bmp|webp/.test(type); }

function updateDocCount() {
	const el = document.getElementById("doc-count");
	if (el) el.textContent = documents.length ? `${documents.length} file${documents.length > 1 ? "s" : ""}` : "";
}

function renderDocuments() {
	const list = document.getElementById("doc-list");
	if (!list) return;
	list.replaceChildren();
	updateDocCount();
	if (!documents.length) {
		list.innerHTML = '<div class="doc-empty">Upload a PDF, Excel, or image to analyse</div>';
		return;
	}
	documents.forEach((doc) => {
		const item = document.createElement("div");
		item.className = "doc-item";
		const isImg = isImageType(doc.file_type);
		item.innerHTML = `<span class="doc-icon">${getDocIcon(doc.file_type)}</span><span class="doc-name" title="${escapeHtml(doc.file_name)}">${escapeHtml(doc.file_name)}</span><span class="doc-actions">${isImg ? '<button class="doc-action" data-action="analyse">Analyse</button><button class="doc-action" data-action="ocr">OCR</button>' : '<button class="doc-action" data-action="summarise">Summarise</button><button class="doc-action" data-action="tables">Tables</button>'}<button class="doc-remove" data-action="remove">✕</button></span>`;
		if (isImg) {
			item.querySelector("[data-action=analyse]").addEventListener("click", (e) => { e.stopPropagation(); askAboutImage(doc, "Analyse this image and describe what you see in detail."); });
			item.querySelector("[data-action=ocr]").addEventListener("click", (e) => { e.stopPropagation(); askAboutImage(doc, "Extract all text from this image. Read every visible word and character."); });
		} else {
			item.querySelector("[data-action=summarise]").addEventListener("click", (e) => { e.stopPropagation(); askAboutDocument(doc, "Please summarise this document."); });
			item.querySelector("[data-action=tables]").addEventListener("click", (e) => { e.stopPropagation(); askAboutDocument(doc, "Please extract all tables from this document and show them."); });
		}
		item.querySelector("[data-action=remove]").addEventListener("click", (e) => { e.stopPropagation(); deleteDocument(doc.name); });
		list.appendChild(item);
	});
}

async function uploadDocument(file) {
	const formData = new FormData();
	formData.append("file", file);
	formData.append("is_private", "1");
	showToast(`Uploading ${file.name}…`);
	try {
		const resp = await fetch("/api/method/chatbot.document_processor.upload_file", {
			method: "POST",
			headers: { "X-Frappe-CSRF-Token": csrf },
			body: formData,
		});
		const data = await resp.json();
		if (!resp.ok) throw new Error(data?.exc || "Upload failed");
		const doc = data.message;
		documents.unshift(doc);
		persistDocuments();
		renderDocuments();
		showToast(`Uploaded ${doc.file_name}`);
		return doc;
	} catch (err) {
		showToast(`Upload failed: ${err.message}`);
		throw err;
	}
}

async function deleteDocument(fileName) {
	try {
		const resp = await fetch("/api/method/chatbot.document_processor.delete_document", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
			body: JSON.stringify({ file_name: fileName }),
		});
		const data = await resp.json();
		if (!resp.ok) throw new Error(data?.exc || "Delete failed");
		documents = documents.filter((d) => d.name !== fileName);
		persistDocuments();
		renderDocuments();
		showToast("Document removed");
	} catch (err) {
		showToast(`Failed to remove: ${err.message}`);
	}
}

async function askAboutImage(doc, message) {
	setComposerState(true);
	removeWelcome();
	createMessage(message, "user");
	addToConversation("user", `${message} [Image: ${doc.file_name}]`);
	const pending = createMessage("", "ai", true);
	try {
		const imgResp = await fetch("/api/method/chatbot.document_processor.get_image_data", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
			body: JSON.stringify({ file_name: doc.name }),
		});
		const imgData = await imgResp.json();
		if (!imgResp.ok) throw new Error(imgData?.exc || "Could not read image");
		const chatResp = await fetch("/api/method/chatbot.ai_agent.chat", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
			body: JSON.stringify({ message, image_data: imgData.message.data, image_mime_type: imgData.message.mime_type, target_language: targetLanguage || undefined }),
		});
		const chatData = await chatResp.json();
		if (!chatResp.ok) throw new Error(chatData?.exc || "No response");
		const reply = chatData?.message?.reply || "I'm sorry, I couldn't analyse the image just now.";
		const action = chatData?.message?.action || null;
		pending.bubble.classList.remove("typing");
		pending.bubble.innerHTML = formatAssistantReply(reply);
		if (action) pending.contentWrap.appendChild(createActionCard(action));
		addCopyButton(pending.contentWrap, reply);
		addToConversation("ai", reply, action);
	} catch (error) {
		pending.bubble.classList.remove("typing");
		pending.bubble.textContent = "Something went wrong while analysing the image. Please try again.";
		console.error("Image query failed:", error);
	} finally {
		setComposerState(false);
		messageInput.focus();
		scrollToBottom();
	}
}

async function askAboutDocument(doc, message) {
	setComposerState(true);
	removeWelcome();
	createMessage(message, "user");
	addToConversation("user", `${message} [File: ${doc.file_name}]`);
	const pending = createMessage("", "ai", true);
	try {
		const contentResp = await fetch("/api/method/chatbot.document_processor.get_document_content", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
			body: JSON.stringify({ file_name: doc.name }),
		});
		const contentData = await contentResp.json();
		if (!contentResp.ok) throw new Error(contentData?.exc || "Could not read document");
		const chatResp = await fetch("/api/method/chatbot.ai_agent.chat", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
			body: JSON.stringify({ message, document_content: contentData.message.content, target_language: targetLanguage || undefined }),
		});
		const chatData = await chatResp.json();
		if (!chatResp.ok) throw new Error(chatData?.exc || "No response");
		const reply = chatData?.message?.reply || "I'm sorry, I couldn't generate a response just now.";
		const action = chatData?.message?.action || null;
		pending.bubble.classList.remove("typing");
		pending.bubble.innerHTML = formatAssistantReply(reply);
		if (action) pending.contentWrap.appendChild(createActionCard(action));
		addCopyButton(pending.contentWrap, reply);
		addToConversation("ai", reply, action);
	} catch (error) {
		pending.bubble.classList.remove("typing");
		pending.bubble.textContent = "Something went wrong while processing the document. Please try again.";
		console.error("Document query failed:", error);
	} finally {
		setComposerState(false);
		messageInput.focus();
		scrollToBottom();
	}
}

function deleteConversation(id, event) {
	if (event) event.stopPropagation();
	if (!confirm("Delete this conversation?")) return;
	const idx = conversations.findIndex((c) => c.id === id);
	if (idx === -1) return;
	conversations.splice(idx, 1);
	if (id === activeConversationId) {
		activeConversationId = conversations[0]?.id || createConversation();
	}
	persistConversations();
	renderHistory();
	renderConversation();
}

function clearAllConversations() {
	if (!conversations.length) return;
	if (!confirm("Delete all conversations?")) return;
	conversations = [];
	activeConversationId = createConversation();
	persistConversations();
	renderHistory();
	renderConversation();
}

function renderHistory() {
	historyList.replaceChildren();
	const clearEl = document.getElementById("clear-all");
	if (clearEl) clearEl.style.display = conversations.length ? "" : "none";
	if (!conversations.length) {
		historyList.innerHTML = '<div class="history-empty">No conversations yet</div>';
		return;
	}
	conversations.forEach((conversation) => {
		const item = document.createElement("div");
		item.className = "history-item" + (conversation.id === activeConversationId ? " active" : "");
		item.innerHTML = `<span class="h-title">${escapeHtml(conversation.title)}</span><button class="h-del" title="Delete conversation">✕</button>`;
		item.addEventListener("click", () => selectConversation(conversation.id));
		item.querySelector(".h-del").addEventListener("click", (e) => deleteConversation(conversation.id, e));
		historyList.appendChild(item);
	});
}

function renderWelcome() {
	chatBox.innerHTML = `<section class="welcome" id="welcome"><p class="eyebrow">Your work companion</p><h2>What can I help you<br>move forward today?</h2><p>Ask a question, explore an idea, upload a document, or get a quick hand with your next task.</p><div class="suggestions"><button class="suggestion" type="button">Summarise a document</button><button class="suggestion" type="button">Analyse an image</button><button class="suggestion" type="button">Import data from Excel</button><button class="suggestion" type="button">Create an API endpoint</button><button class="suggestion" type="button">Translate to Spanish</button></div></section>`;
	bindSuggestions();
}

function renderConversation() {
	const conversation = activeConversation();
	chatBox.replaceChildren();
	if (!conversation?.messages.length) { renderWelcome(); return; }
	conversation.messages.forEach(({ role, content, action }, index) => {
		const message = createMessage(content, role);
		if (role === "ai") {
			message.bubble.innerHTML = formatAssistantReply(content);
			if (action) message.contentWrap.appendChild(createActionCard(action));
			addCopyButton(message.contentWrap, content, "Copy");
		} else {
			addEditButton(message.contentWrap, index, content);
			addCopyButton(message.contentWrap, content, "Copy");
		}
		addTranslateButton(message.contentWrap, content, role);
	});
	scrollToBottom();
}

function selectConversation(id) {
	if (id === activeConversationId || isSending) return;
	activeConversationId = id;
	renderHistory();
	renderConversation();
}

function startNewConversation() {
	if (isSending) return;
	activeConversationId = createConversation();
	renderHistory();
	renderConversation();
	messageInput.focus();
}

function showToast(msg) {
	const toast = document.getElementById("share-toast");
	if (!toast) return;
	toast.textContent = msg;
	toast.classList.add("show");
	clearTimeout(toast._hide);
	toast._hide = setTimeout(() => toast.classList.remove("show"), 2200);
}

function shareConversation() {
	const conversation = activeConversation();
	if (!conversation?.messages.length) { showToast("No messages to share"); return; }
	const text = conversation.messages.map(({ role, content }) => `${role === "user" ? "You" : "Assistant"}:\n${content}`).join("\n\n");
	const shareData = { title: conversation.title, text: `${conversation.title}\n\n${text}` };
	if (navigator.share && window.matchMedia("(max-width: 720px)").matches) { navigator.share(shareData).catch(() => {}); return; }
	navigator.clipboard.writeText(shareData.text).then(() => { showToast("Copied to clipboard — ready to share!"); }).catch(() => { showToast("Could not copy to clipboard"); });
}

function exportConversation() {
	const conversation = activeConversation();
	if (!conversation?.messages.length) return;
	const text = conversation.messages.map(({ role, content }) => `${role === "user" ? "You" : "Assistant"}:\n${content}`).join("\n\n");
	const blob = new Blob([`${conversation.title}\n\n${text}\n`], { type: "text/plain" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = "ai-conversation.txt";
	link.click();
	URL.revokeObjectURL(url);
}

async function sendMsg(message = messageInput.value.trim()) {
	if (!message || isSending) return;
	createMessage(message, "user");
	addToConversation("user", message);
	messageInput.value = "";
	resizeInput();
	setComposerState(true);
	const conversationId = activeConversationId;
	const pending = createMessage("", "ai", true);
	try {
		const response = await fetch("/api/method/chatbot.ai_agent.chat", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
			body: JSON.stringify({ message, target_language: targetLanguage || undefined }),
		});
		const data = await response.json();
		if (!response.ok) throw new Error(data?.exc || "The assistant could not respond.");
		const reply = data?.message?.reply || "I'm sorry, I couldn't generate a response just now.";
		const action = data?.message?.action || null;
		pending.bubble.classList.remove("typing");
		pending.bubble.innerHTML = formatAssistantReply(reply);
		if (action) pending.contentWrap.appendChild(createActionCard(action));
		addCopyButton(pending.contentWrap, reply);
		addToConversation("ai", reply, action);
	} catch (error) {
		pending.bubble.classList.remove("typing");
		pending.bubble.textContent = "Something went wrong. Please try again.";
		addRetryButton(pending.contentWrap, message, conversationId);
		console.error("Chat request failed:", error);
		setStatus("error", "Failed");
	} finally {
		setComposerState(false);
		messageInput.focus();
		scrollToBottom();
	}
}

function resizeInput() {
	messageInput.style.height = "auto";
	messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
}

function startVoice() {
	const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
	if (!Recognition) { messageInput.placeholder = "Voice not supported"; return; }
	const recognition = new Recognition();
	recognition.lang = "en-US";
	recognition.interimResults = true;
	const voiceButton = document.getElementById("voice-button");
	voiceButton.classList.add("recording");
	voiceButton.setAttribute("aria-label", "Listening...");
	recognition.onresult = (event) => {
		messageInput.value = Array.from(event.results).map((r) => r[0].transcript).join("");
		resizeInput();
		messageInput.focus();
	};
	recognition.onerror = () => { messageInput.placeholder = "Couldn't hear that. Try again."; };
	recognition.onend = () => { voiceButton.classList.remove("recording"); voiceButton.setAttribute("aria-label", "Use voice input"); };
	recognition.start();
}

function bindSuggestions() {
	document.querySelectorAll(".suggestion").forEach((button) => {
		button.addEventListener("click", () => sendMsg(button.textContent));
	});
}

document.getElementById("chat-form").addEventListener("submit", (event) => { event.preventDefault(); sendMsg(); });
messageInput.addEventListener("input", resizeInput);
messageInput.addEventListener("keydown", (event) => {
	if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMsg(); }
});
document.addEventListener("keydown", (e) => {
	if ((e.ctrlKey || e.metaKey) && e.key === "n") { e.preventDefault(); startNewConversation(); }
});
document.getElementById("voice-button").addEventListener("click", startVoice);
document.getElementById("new-chat").addEventListener("click", startNewConversation);
document.getElementById("share-chat").addEventListener("click", shareConversation);
document.getElementById("export-chat").addEventListener("click", exportConversation);
document.getElementById("clear-all").addEventListener("click", clearAllConversations);

const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-button");
const uploadLink = document.getElementById("upload-link");
const composer = document.getElementById("chat-form");
function openFilePicker() { fileInput.click(); }
uploadBtn.addEventListener("click", openFilePicker);
uploadLink.addEventListener("click", openFilePicker);

composer.addEventListener("dragover", (e) => { e.preventDefault(); composer.classList.add("dragover"); });
composer.addEventListener("dragleave", () => { composer.classList.remove("dragover"); });
composer.addEventListener("drop", (e) => {
	e.preventDefault();
	composer.classList.remove("dragover");
	const files = Array.from(e.dataTransfer.files).filter((f) => /\.(pdf|docx?|xlsx?|csv|pptx?|png|jpe?g|gif|bmp|webp)$/i.test(f.name));
	if (!files.length) { showToast("Drop a supported file"); return; }
	files.forEach((f) => uploadDocument(f));
});

fileInput.addEventListener("change", async () => {
	const files = Array.from(fileInput.files);
	fileInput.value = "";
	for (const file of files) {
		if (!/\.(pdf|docx?|xlsx?|csv|pptx?|png|jpe?g|gif|bmp|webp)$/i.test(file.name)) { showToast(`Skipped: ${file.name}`); continue; }
		await uploadDocument(file);
	}
});

const langSelect = document.getElementById("lang-select");
langSelect.value = targetLanguage;
langSelect.addEventListener("change", () => {
	targetLanguage = langSelect.value;
	persistLanguage(targetLanguage);
	showToast(targetLanguage ? `Response language: ${targetLanguage}` : "Auto-detect");
});

renderHistory();
renderDocuments();
bindSuggestions();
})();

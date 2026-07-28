(function () {
const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("msg");
const sendButton = document.getElementById("send-button");
const historyList = document.getElementById("history");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const storageKey = "chatbot.conversations.v2";
const docsKey = "chatbot.documents.v1";
const langKey = "chatbot.language.v1";
const maxConversations = 12;
const copyIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const checkIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
const downloadIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';

function guessExtension(code) {
	const firstLine = code.trim().split("\n")[0];
	if (/^(import |from |def |class |#!|print|return )/.test(firstLine) || /\bpython\b/i.test(code.slice(0, 200))) return "py";
	if (/^(const |let |var |function |import |export |class |async |await )/.test(firstLine) || /=>/.test(firstLine)) return "js";
	if (/^<!DOCTYPE html|<html/i.test(firstLine)) return "html";
	if (/^{[\s\S]*}$/.test(code.trim()) && /[{};]/.test(code)) return "css";
	if (/^SELECT |^INSERT |^UPDATE |^DELETE |^CREATE |^ALTER /i.test(firstLine)) return "sql";
	if (/^# |^## |^### /.test(firstLine) && /[*[\]()]/.test(code)) return "md";
	if (/^\{$/.test(firstLine) && /"/.test(code)) return "json";
	if (/^<\?php/.test(firstLine)) return "php";
	if (/^#!\/bin\/(bash|sh)/.test(firstLine)) return "sh";
	return "txt";
}
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

function addToConversation(role, content, action, chart, dataTable) {
	const conversation = activeConversation();
	if (!conversation) return;
	conversation.messages.push({ role, content, action, chart, dataTable });
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
	const raw = String(reply).replace(/\r\n/g, "\n");
	const codeBlocks = [];
	const withoutCode = raw.replace(/```([^`]*)```/g, (_, code) => {
		codeBlocks.push(code.trim());
		return `@@CODE_${codeBlocks.length - 1}@@`;
	});
	const escaped = escapeHtml(withoutCode);
	const inline = (text) => text.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>");
	const lines = escaped.split("\n");
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
	return output.join("").replace(/@@CODE_(\d+)@@/g, (_, index) => {
		const codeText = codeBlocks[index];
		const escapedCode = escapeHtml(codeText);
		const ext = guessExtension(codeText);
		const filename = `code-${index + 1}.${ext}`;
		return `<div class="code-block-wrapper"><div class="code-actions"><button class="code-copy-btn" type="button" aria-label="Copy code">${copyIcon}</button><button class="code-dl-btn" type="button" data-filename="${filename}" aria-label="Download ${filename}">${downloadIcon}</button></div><pre><code>${escapedCode}</code></pre></div>`;
	});
}

function createActionCard(action) {
	if (!action) return;
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
	} else if (action.type === "image_generated") {
		card.className = "action-card image-card";
		card.innerHTML = `<div class="image-card-preview"><img src="${escapeHtml(action.image_url)}" alt="${escapeHtml(action.prompt)}" loading="lazy" onerror="this.closest('.image-card')?.querySelector('.image-card-fallback')?.classList.add('show')"/><div class="image-card-fallback"><p>Image could not be loaded.</p><a href="${escapeHtml(action.image_url)}" target="_blank" rel="noopener">Open in new tab</a></div></div><div class="action-card-body"><a href="${escapeHtml(action.image_url)}" target="_blank" rel="noopener" class="btn">Download</a></div>`;
	} else if (action.type === "report_created") {
		card.innerHTML = `<div class="action-card-icon">📈</div><div class="action-card-body"><strong>Report Created</strong><div class="action-card-details"><span>${escapeHtml(action.report_name)}</span><span>DocType: ${escapeHtml(action.doctype)}</span>${action.chart_type ? `<span class="badge success">Chart: ${escapeHtml(action.chart_type)}</span>` : ""}<a href="${escapeHtml(action.report_url)}" target="_blank" class="btn">Open Report</a></div></div>`;
	} else if (action.type === "data_queried") {
		card.innerHTML = `<div class="action-card-icon">🔍</div><div class="action-card-body"><strong>Data Query Complete</strong><div class="action-card-details"><span>${action.count} records from ${escapeHtml(action.doctype)}</span></div></div>`;
	} else if (action.type === "data_chart") {
		card.innerHTML = `<div class="action-card-icon">📊</div><div class="action-card-body"><strong>Chart: ${escapeHtml(action.title)}</strong><div class="action-card-details"><span class="badge success">${escapeHtml(action.chart_type)}</span></div></div>`;
	} else if (action.type === "data_exported") {
		card.innerHTML = `<div class="action-card-icon">📦</div><div class="action-card-body"><strong>Data Exported</strong><div class="action-card-details"><span>${action.count} records</span><span>Format: ${escapeHtml(action.format)}</span><a href="${escapeHtml(action.file_url)}" target="_blank" class="btn">Download</a></div></div>`;
	} else if (action.type === "workflow_created" || action.type === "workflow_updated") {
		const stateBadges = (action.states || []).map((s) => `<span class="badge success">${escapeHtml(s)}</span>`).join(" ");
		card.innerHTML = `<div class="action-card-icon">⚙️</div><div class="action-card-body"><strong>Workflow ${action.type === "workflow_created" ? "Created" : "Updated"}</strong><div class="action-card-details"><span>${escapeHtml(action.workflow_name)}</span><span>DocType: ${escapeHtml(action.doctype)}</span><span>${action.transitions} transitions</span></div><div style="margin-top:6px">${stateBadges}</div></div>`;
	} else if (action.type === "email_sent") {
		card.innerHTML = `<div class="action-card-icon">📧</div><div class="action-card-body"><strong>Email Sent</strong><div class="action-card-details"><span>To: ${escapeHtml(action.recipients)}</span><span>Subject: ${escapeHtml(action.subject)}</span></div></div>`;
	} else if (action.type === "email_drafted") {
		card.innerHTML = `<div class="action-card-icon">📝</div><div class="action-card-body"><strong>Email Draft Saved</strong><div class="action-card-details"><span>To: ${escapeHtml(action.recipients)}</span><span>Subject: ${escapeHtml(action.subject)}</span></div></div>`;
	} else if (action.type === "email_template_created" || action.type === "email_template_updated") {
		card.innerHTML = `<div class="action-card-icon">📋</div><div class="action-card-body"><strong>Email Template ${action.type === "email_template_created" ? "Created" : "Updated"}</strong><div class="action-card-details"><span>${escapeHtml(action.template_name)}</span><span>DocType: ${escapeHtml(action.doctype)}</span></div></div>`;
	} else if (action.type === "document_created" || action.type === "document_updated") {
		card.innerHTML = `<div class="action-card-icon">📄</div><div class="action-card-body"><strong>${action.type === "document_created" ? "Document Created" : "Document Updated"}</strong><div class="action-card-details"><span>${escapeHtml(action.doctype)}</span><span>${escapeHtml(action.name)}</span><a href="${escapeHtml(action.url)}" target="_blank" class="btn">Open</a></div></div>`;
	} else if (action.type === "notification_created" || action.type === "notification_updated") {
		card.innerHTML = `<div class="action-card-icon">🔔</div><div class="action-card-body"><strong>Notification ${action.type === "notification_created" ? "Created" : "Updated"}</strong><div class="action-card-details"><span>DocType: ${escapeHtml(action.doctype)}</span><span>Event: ${escapeHtml(action.event)}</span></div></div>`;
	}
	return card;
}

function renderChart(chartData) {
	if (!chartData || !chartData.labels || !chartData.datasets) return;
	const wrapper = document.createElement("div");
	wrapper.className = "chart-wrapper";
	wrapper.style.cssText = "margin: 12px 0; padding: 16px; background: #fff; border: 1px solid var(--line); border-radius: 10px;";
	if (chartData.title) {
		const title = document.createElement("div");
		title.style.cssText = "font-weight: 600; font-size: 14px; margin-bottom: 10px; color: var(--ink);";
		title.textContent = chartData.title;
		wrapper.appendChild(title);
	}
	const canvas = document.createElement("canvas");
	canvas.width = 400;
	canvas.height = 220;
	canvas.style.cssText = "width: 100%; max-width: 600px; height: 220px;";
	wrapper.appendChild(canvas);
	const ctx = canvas.getContext("2d");

	const labels = chartData.labels.slice(0, 20);
	const datasets = chartData.datasets;
	const type = chartData.type || "bar";
	const colors = ["#1c7168", "#e8b84b", "#d9534f", "#4a90d9", "#50b89a", "#9b59b6", "#e67e22", "#2ecc71"];

	const padding = { top: 20, right: 20, bottom: 40, left: 50 };
	const chartW = canvas.width - padding.left - padding.right;
	const chartH = canvas.height - padding.top - padding.bottom;

	const allValues = datasets.flatMap((ds) => ds.values || []);
	const maxVal = Math.max(...allValues, 1);
	const minVal = 0;

	function drawBarChart() {
		const groupW = chartW / labels.length;
		const barW = Math.max(groupW / datasets.length - 4, 4);
		datasets.forEach((ds, di) => {
			(ds.values || []).slice(0, labels.length).forEach((val, i) => {
				const x = padding.left + i * groupW + di * (barW + 2) + 2;
				const h = ((val - minVal) / (maxVal - minVal)) * chartH;
				const y = padding.top + chartH - h;
				ctx.fillStyle = colors[di % colors.length];
				ctx.fillRect(x, y, barW, h);
				if (val > 0 && h > 15) {
					ctx.fillStyle = "#1d2939";
					ctx.font = "9px DM Sans, sans-serif";
					ctx.textAlign = "center";
					ctx.fillText(val, x + barW / 2, y - 3);
				}
			});
		});
	}

	function drawLineChart() {
		datasets.forEach((ds, di) => {
			const pts = (ds.values || []).slice(0, labels.length);
			ctx.strokeStyle = colors[di % colors.length];
			ctx.lineWidth = 2;
			ctx.beginPath();
			pts.forEach((val, i) => {
				const x = padding.left + (i / Math.max(pts.length - 1, 1)) * chartW;
				const y = padding.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
				i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
			});
			ctx.stroke();
			ctx.fillStyle = colors[di % colors.length];
			pts.forEach((val, i) => {
				const x = padding.left + (i / Math.max(pts.length - 1, 1)) * chartW;
				const y = padding.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
				ctx.beginPath();
				ctx.arc(x, y, 3, 0, Math.PI * 2);
				ctx.fill();
			});
		});
	}

	function drawPieChart() {
		const cx = canvas.width / 2;
		const cy = canvas.height / 2 + 10;
		const r = Math.min(chartW, chartH) / 2 - 10;
		const total = allValues.reduce((a, b) => a + b, 0);
		if (!total) return;
		let startAngle = -Math.PI / 2;
		allValues.slice(0, labels.length).forEach((val, i) => {
			const sliceAngle = (val / total) * Math.PI * 2;
			ctx.fillStyle = colors[i % colors.length];
			ctx.beginPath();
			ctx.moveTo(cx, cy);
			ctx.arc(cx, cy, r, startAngle, startAngle + sliceAngle);
			ctx.closePath();
			ctx.fill();
			startAngle += sliceAngle;
		});
		const legendY = canvas.height - 18;
		labels.slice(0, 8).forEach((label, i) => {
			const lx = 10 + i * 75;
			ctx.fillStyle = colors[i % colors.length];
			ctx.fillRect(lx, legendY - 6, 8, 8);
			ctx.fillStyle = "#1d2939";
			ctx.font = "9px DM Sans, sans-serif";
			ctx.fillText(label.slice(0, 10), lx + 11, legendY + 1);
		});
	}

	ctx.clearRect(0, 0, canvas.width, canvas.height);

	if (type === "pie" || type === "doughnut") {
		drawPieChart();
	} else if (type === "line") {
		drawLineChart();
	} else {
		drawBarChart();
	}

	ctx.strokeStyle = "#e8e5df";
	ctx.lineWidth = 1;
	ctx.beginPath();
	ctx.moveTo(padding.left, padding.top);
	ctx.lineTo(padding.left, padding.top + chartH);
	ctx.lineTo(padding.left + chartW, padding.top + chartH);
	ctx.stroke();

	if (type !== "pie" && type !== "doughnut") {
		const step = maxVal / 4;
		for (let i = 0; i <= 4; i++) {
			const val = Math.round(minVal + (step * i) * 100) / 100;
			const y = padding.top + chartH - (i / 4) * chartH;
			ctx.fillStyle = "#98a2b3";
			ctx.font = "9px DM Sans, sans-serif";
			ctx.textAlign = "right";
			ctx.fillText(val, padding.left - 5, y + 3);
		}
		const labelStep = Math.max(1, Math.floor(labels.length / 8));
		labels.forEach((label, i) => {
			if (i % labelStep !== 0 && i !== labels.length - 1) return;
			const x = padding.left + (i / Math.max(labels.length - 1, 1)) * chartW;
			ctx.fillStyle = "#98a2b3";
			ctx.font = "9px DM Sans, sans-serif";
			ctx.textAlign = "center";
			ctx.fillText(label.slice(0, 12), x, padding.top + chartH + 14);
		});
	}

	return wrapper;
}

function createDataTable(data) {
	if (!data || !data.columns || !data.rows || !data.rows.length) return;
	const wrapper = document.createElement("div");
	wrapper.style.cssText = "margin: 10px 0; overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: #fff;";
	const table = document.createElement("table");
	table.style.cssText = "width: 100%; border-collapse: collapse; font-size: 12px;";
	const thead = document.createElement("thead");
	const headerRow = document.createElement("tr");
	headerRow.style.cssText = "background: var(--teal-soft);";
	data.columns.forEach((col) => {
		const th = document.createElement("th");
		th.style.cssText = "padding: 8px 10px; text-align: left; font-weight: 600; color: var(--navy); white-space: nowrap;";
		th.textContent = col.label || col.fieldname;
		headerRow.appendChild(th);
	});
	thead.appendChild(headerRow);
	table.appendChild(thead);
	const tbody = document.createElement("tbody");
	const maxRows = Math.min(data.rows.length, 25);
	for (let i = 0; i < maxRows; i++) {
		const row = document.createElement("tr");
		row.style.cssText = i % 2 === 0 ? "background: #fff;" : "background: #faf8f4;";
		data.columns.forEach((col) => {
			const td = document.createElement("td");
			td.style.cssText = "padding: 6px 10px; border-top: 1px solid var(--line); white-space: nowrap;";
			let val = data.rows[i][col.fieldname];
			if (typeof val === "number") {
				td.style.textAlign = "right";
				td.textContent = val.toLocaleString();
			} else {
				td.textContent = val != null ? String(val) : "";
			}
			row.appendChild(td);
		});
		tbody.appendChild(row);
	}
	table.appendChild(tbody);
	wrapper.appendChild(table);
	if (data.total_rows > maxRows) {
		const note = document.createElement("div");
		note.style.cssText = "padding: 6px 10px; color: var(--muted); font-size: 11px; border-top: 1px solid var(--line);";
		note.textContent = `Showing ${maxRows} of ${data.total_rows} records`;
		wrapper.appendChild(note);
	}
	return wrapper;
}

function appendDataAndChart(contentWrap, msgData) {
	if (msgData.chart) {
		const chartEl = renderChart(msgData.chart);
		if (chartEl) contentWrap.appendChild(chartEl);
	}
	if (msgData.data) {
		const tableEl = createDataTable(msgData.data);
		if (tableEl) contentWrap.appendChild(tableEl);
	}
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

function addCopyButton(contentWrap, text) {
	const actions = document.createElement("div");
	actions.className = "message-actions";
	const button = document.createElement("button");
	button.type = "button";
	button.className = "copy-btn";
	button.ariaLabel = "Copy";
	button.innerHTML = copyIcon;
	button.addEventListener("click", async () => {
		try {
			await navigator.clipboard.writeText(text);
			button.innerHTML = checkIcon;
			setTimeout(() => { button.innerHTML = copyIcon; }, 1500);
		} catch {
			button.textContent = "!";
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
		const msgData = chatData?.message || {};
		pending.bubble.classList.remove("typing");
		pending.bubble.innerHTML = formatAssistantReply(reply);
		if (action) pending.contentWrap.appendChild(createActionCard(action));
		appendDataAndChart(pending.contentWrap, msgData);
		addCopyButton(pending.contentWrap, reply);
		addToConversation("ai", reply, action, msgData.chart, msgData.data);
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
		const msgData = chatData?.message || {};
		pending.bubble.classList.remove("typing");
		pending.bubble.innerHTML = formatAssistantReply(reply);
		if (action) pending.contentWrap.appendChild(createActionCard(action));
		appendDataAndChart(pending.contentWrap, msgData);
		addCopyButton(pending.contentWrap, reply);
		addToConversation("ai", reply, action, msgData.chart, msgData.data);
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
	chatBox.innerHTML = `<section class="welcome" id="welcome"><p class="eyebrow">Your work companion</p><h2>What can I help you<br>move forward today?</h2><p>Ask a question, explore an idea, upload a document, or get a quick hand with your next task.</p><div class="suggestions"><button class="suggestion" type="button">Summarise a document</button><button class="suggestion" type="button">Analyse an image</button><button class="suggestion" type="button">Import data from Excel</button><button class="suggestion" type="button">Build a report</button><button class="suggestion" type="button">Create a workflow</button><button class="suggestion" type="button">Show me sales data</button></div></section>`;
	bindSuggestions();
}

function renderConversation() {
	const conversation = activeConversation();
	chatBox.replaceChildren();
	if (!conversation?.messages.length) { renderWelcome(); return; }
	conversation.messages.forEach(({ role, content, action, chart, dataTable }, index) => {
		const message = createMessage(content, role);
		if (role === "ai") {
			message.bubble.innerHTML = formatAssistantReply(content);
			if (action) message.contentWrap.appendChild(createActionCard(action));
			if (chart) {
				const chartEl = renderChart(chart);
				if (chartEl) message.contentWrap.appendChild(chartEl);
			}
			if (dataTable) {
				const tableEl = createDataTable(dataTable);
				if (tableEl) message.contentWrap.appendChild(tableEl);
			}
			addCopyButton(message.contentWrap, content);
		} else {
			addEditButton(message.contentWrap, index, content);
			addCopyButton(message.contentWrap, content);
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
		const msgData = data?.message || {};
		pending.bubble.classList.remove("typing");
		pending.bubble.innerHTML = formatAssistantReply(reply);
		if (action) pending.contentWrap.appendChild(createActionCard(action));
		appendDataAndChart(pending.contentWrap, msgData);
		addCopyButton(pending.contentWrap, reply);
		addToConversation("ai", reply, action, msgData.chart, msgData.data);
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

chatBox.addEventListener("click", (e) => {
	const wrapper = e.target.closest(".code-block-wrapper");
	if (!wrapper) return;
	const code = wrapper.querySelector("pre code");
	if (!code) return;
	const copyBtn = e.target.closest(".code-copy-btn");
	if (copyBtn) {
		navigator.clipboard.writeText(code.textContent).then(() => {
			copyBtn.innerHTML = checkIcon;
			setTimeout(() => { copyBtn.innerHTML = copyIcon; }, 1500);
		}).catch(() => {});
		return;
	}
	const dlBtn = e.target.closest(".code-dl-btn");
	if (dlBtn) {
		const filename = dlBtn.dataset.filename || "code.txt";
		const blob = new Blob([code.textContent], { type: "text/plain" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = filename;
		link.click();
		URL.revokeObjectURL(url);
		dlBtn.innerHTML = checkIcon;
		setTimeout(() => { dlBtn.innerHTML = downloadIcon; }, 1500);
	}
});

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
renderConversation();
renderDocuments();
bindSuggestions();

// ─── Plugins Workspace ─────────────────────────────────────────────

const chatShell = document.getElementById("chat-shell");
const pluginsView = document.getElementById("plugins-view");
const pluginsList = document.getElementById("plugins-list");
const navChat = document.getElementById("nav-chat");
const navPlugins = document.getElementById("nav-plugins");
const refreshBtn = document.getElementById("refresh-plugins");
const topbarTitle = document.getElementById("topbar-title");

let currentView = "chat";

function switchView(view) {
	currentView = view;
	navChat.classList.toggle("active", view === "chat");
	navPlugins.classList.toggle("active", view === "plugins");
	chatShell.classList.toggle("hidden", view !== "chat");
	pluginsView.classList.toggle("active", view === "plugins");
	topbarTitle.textContent = view === "chat" ? "AI Assistant" : "Plugins Workspace";
	langSelect.style.display = view === "chat" ? "" : "none";
	document.getElementById("share-chat").style.display = view === "chat" ? "" : "none";
	document.getElementById("export-chat").style.display = view === "chat" ? "" : "none";
	refreshBtn.style.display = view === "plugins" ? "" : "none";
	if (view === "plugins") loadPlugins();
}

function showPluginsToast(msg) {
	let toast = document.querySelector(".plugins-toast");
	if (!toast) {
		toast = document.createElement("div");
		toast.className = "plugins-toast";
		document.body.appendChild(toast);
	}
	toast.textContent = msg;
	toast.classList.add("show");
	clearTimeout(toast._hide);
	toast._hide = setTimeout(() => toast.classList.remove("show"), 2200);
}

function getPluginIcon(name) {
	const icons = {
		greeting: "👋",
		audit_log: "📋",
		rate_limiter: "⏱",
	};
	return icons[name] || "🧩";
}

function getHookLabel(hook) {
	const labels = {
		on_register: "Register",
		on_chat_before: "Before Chat",
		on_chat_after: "After Chat",
		on_tool_before: "Before Tool",
		on_tool_after: "After Tool",
	};
	return labels[hook] || hook;
}

async function loadPlugins() {
	pluginsList.innerHTML = '<div class="plugins-loading"><span class="spinner"></span> Loading plugins...</div>';
	try {
		const resp = await fetch("/api/method/chatbot.plugin_api.get_plugins", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
		});
		const data = await resp.json();
		if (!resp.ok) throw new Error(data?.exc || "Failed to load plugins");
		const plugins = data.message || [];
		renderPlugins(plugins);
	} catch (err) {
		pluginsList.innerHTML = `<div class="plugins-error">Failed to load plugins: ${escapeHtml(err.message)}</div>`;
	}
}

function renderPlugins(plugins) {
	if (!plugins.length) {
		pluginsList.innerHTML = '<div class="plugins-empty">No plugins registered.</div>';
		return;
	}
	pluginsList.replaceChildren();
	plugins.forEach((plugin) => {
		const card = document.createElement("div");
		card.className = "plugin-card";
		const isOn = plugin.enabled;
		card.innerHTML = `
			<div class="plugin-icon ${isOn ? "on" : "off"}">${getPluginIcon(plugin.name)}</div>
			<div class="plugin-info">
				<div class="plugin-name">${escapeHtml(plugin.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()))}</div>
				<div class="plugin-desc">${escapeHtml(plugin.description)}</div>
				<div class="plugin-meta">
					<span class="version-badge">v${escapeHtml(plugin.version)}</span>
					${(plugin.hooks || []).map((h) => `<span class="hook-badge">${getHookLabel(h)}</span>`).join("")}
				</div>
			</div>
			<div class="plugin-toggle">
				<label class="toggle-switch">
					<input type="checkbox" ${isOn ? "checked" : ""} data-plugin="${escapeHtml(plugin.name)}">
					<span class="toggle-slider"></span>
				</label>
			</div>
		`;
		const toggle = card.querySelector("input");
		toggle.addEventListener("change", () => togglePlugin(plugin.name, toggle));
		pluginsList.appendChild(card);
	});
}

async function togglePlugin(name, checkbox) {
	checkbox.disabled = true;
	try {
		const resp = await fetch("/api/method/chatbot.plugin_api.toggle_plugin", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
			body: JSON.stringify({ plugin_name: name }),
		});
		const data = await resp.json();
		if (!resp.ok) throw new Error(data?.exc || "Toggle failed");
		const enabled = data.message?.enabled;
		checkbox.checked = enabled;
		const icon = checkbox.closest(".plugin-card")?.querySelector(".plugin-icon");
		if (icon) {
			icon.className = `plugin-icon ${enabled ? "on" : "off"}`;
		}
		showPluginsToast(`${name.replace(/_/g, " ")} ${enabled ? "enabled" : "disabled"}`);
	} catch (err) {
		checkbox.checked = !checkbox.checked;
		showPluginsToast(`Failed: ${err.message}`);
	} finally {
		checkbox.disabled = false;
	}
}

navPlugins.addEventListener("click", () => switchView("plugins"));
navChat.addEventListener("click", () => switchView("chat"));
refreshBtn.addEventListener("click", loadPlugins);
})();

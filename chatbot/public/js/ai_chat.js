(function () {
const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("msg");
const sendButton = document.getElementById("send-button");
const historyList = document.getElementById("history");
const storageKey = "chatbot.conversations.v1";
const maxConversations = 12;
let isSending = false;
let conversations = loadConversations();
let activeConversationId = conversations[0]?.id || createConversation();

function scrollToBottom() {
	chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: "smooth" });
}

function removeWelcome() {
	document.getElementById("welcome")?.remove();
}

function createConversation() {
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
	return (
		conversation &&
		typeof conversation.id === "string" &&
		typeof conversation.title === "string" &&
		Array.isArray(conversation.messages)
	);
}

function persistConversations() {
	try {
		window.localStorage.setItem(storageKey, JSON.stringify(conversations.slice(0, maxConversations)));
	} catch (error) {
		console.warn("Unable to save chat history:", error);
	}
}

function activeConversation() {
	return conversations.find((conversation) => conversation.id === activeConversationId);
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
	const element = document.createElement("div");
	element.textContent = value;
	return element.innerHTML;
}

function formatAssistantReply(reply) {
	const escaped = escapeHtml(String(reply)).replace(/\r\n/g, "\n");
	const codeBlocks = [];
	const withoutCodeBlocks = escaped.replace(/```([^`]*)```/g, (_, code) => {
		codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`);
		return `@@CODE_${codeBlocks.length - 1}@@`;
	});
	const inline = (text) => text
		.replace(/`([^`]+)`/g, "<code>$1</code>")
		.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
		.replace(/\*([^*]+)\*/g, "<em>$1</em>");
	const lines = withoutCodeBlocks.split("\n");
	const output = [];
	let listType = null;
	let sectionOpen = false;

	const closeList = () => {
		if (listType) output.push(`</${listType}>`);
		listType = null;
	};

	const closeSection = () => {
		closeList();
		if (sectionOpen) output.push("</section>");
		sectionOpen = false;
	};

	lines.forEach((line, index) => {
		const heading = line.match(/^(#{1,3})\s+(.+)$/);
		const bullet = line.match(/^\s*[-*]\s+(.+)$/);
		const numbered = line.match(/^\s*\d+\.\s+(.+)$/);
		const nextLine = lines.slice(index + 1).find((item) => item.trim());
		const sectionTitle = line.match(/^(.{3,90}):\s*$/);
		const isSectionTitle = sectionTitle && /^\s*(?:[-*]|\d+\.)\s+/.test(nextLine || "");
		if (heading) {
			closeSection();
			const level = heading[1].length;
			output.push(`<h${level}>${inline(heading[2])}</h${level}>`);
		} else if (isSectionTitle) {
			closeSection();
			sectionOpen = true;
			output.push(`<section class="reply-section"><h3>${inline(sectionTitle[1])}</h3>`);
		} else if (bullet || numbered) {
			const nextType = bullet ? "ul" : "ol";
			if (listType && listType !== nextType) closeList();
			if (!listType) { output.push(`<${nextType}>`); listType = nextType; }
			output.push(`<li>${inline((bullet || numbered)[1])}</li>`);
		} else if (line.startsWith("&gt; ")) {
			closeList();
			output.push(`<blockquote>${inline(line.slice(5))}</blockquote>`);
		} else if (line.startsWith("@@CODE_")) {
			closeList();
			output.push(line);
		} else if (line.trim()) {
			closeList();
			output.push(`<p>${inline(line)}</p>`);
		} else {
			closeList();
		}
	});
	closeSection();
	return output.join("").replace(/@@CODE_(\d+)@@/g, (_, index) => codeBlocks[index]);
}

function createActionCard(action) {
	if (!action) return "";
	const card = document.createElement("div");
	card.className = "action-card";

	if (action.type === "data_imported") {
		const success = action.success || 0;
		const failed = action.failed || 0;
		card.innerHTML = `
			<div class="action-card-icon">📊</div>
			<div class="action-card-body">
				<strong>Data Import Complete</strong>
				<div class="action-card-details">
					<span class="badge success">${success} imported</span>
					${failed ? `<span class="badge error">${failed} failed</span>` : ""}
					<span>DocType: ${escapeHtml(action.doctype)}</span>
				</div>
			</div>`;
	} else if (action.type === "api_created") {
		card.innerHTML = `
			<div class="action-card-icon">🔌</div>
			<div class="action-card-body">
				<strong>API Endpoint Created</strong>
				<div class="action-card-details">
					<code>${escapeHtml(action.endpoint_url)}</code>
				</div>
			</div>`;
	} else if (action.type === "client_script_created") {
		card.innerHTML = `
			<div class="action-card-icon">📜</div>
			<div class="action-card-body">
				<strong>Client Script Created</strong>
				<div class="action-card-details">
					<span>${escapeHtml(action.name)}</span>
					<span>DocType: ${escapeHtml(action.doctype)}</span>
				</div>
			</div>`;
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

function addCopyButton(contentWrap, text) {
	const actions = document.createElement("div");
	actions.className = "message-actions";
	const button = document.createElement("button");
	button.type = "button";
	button.className = "copy-btn";
	button.textContent = "Copy response";
	button.addEventListener("click", async () => {
		try {
			await navigator.clipboard.writeText(text);
			button.textContent = "Copied";
			setTimeout(() => { button.textContent = "Copy response"; }, 1500);
		} catch {
			button.textContent = "Copy unavailable";
		}
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
}

function renderHistory() {
	historyList.replaceChildren();
	conversations.forEach((conversation) => {
		const item = document.createElement("button");
		item.type = "button";
		item.className = "history-item";
		item.textContent = conversation.title;
		item.title = conversation.title;
		item.classList.toggle("active", conversation.id === activeConversationId);
		item.addEventListener("click", () => selectConversation(conversation.id));
		historyList.appendChild(item);
	});
}

function renderWelcome() {
	chatBox.innerHTML = `
		<section class="welcome" id="welcome">
			<p class="eyebrow">Your work companion</p>
			<h2>What can I help you<br>move forward today?</h2>
			<p>Ask a question, explore an idea, or get a quick hand with your next task.</p>
			<div class="suggestions">
				<button class="suggestion" type="button">Import data from Excel</button>
				<button class="suggestion" type="button">Create an API endpoint</button>
				<button class="suggestion" type="button">Add validation to Lead form</button>
			</div>
		</section>`;
	bindSuggestions();
}

function renderConversation() {
	const conversation = activeConversation();
	chatBox.replaceChildren();
	if (!conversation?.messages.length) {
		renderWelcome();
		return;
	}
	conversation.messages.forEach(({ role, content, action }) => {
		const message = createMessage(content, role);
		if (role === "ai") {
			message.bubble.innerHTML = formatAssistantReply(content);
			if (action) {
				message.contentWrap.appendChild(createActionCard(action));
			}
			addCopyButton(message.contentWrap, content);
		}
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

function exportConversation() {
	const conversation = activeConversation();
	if (!conversation?.messages.length) return;
	const text = conversation.messages
		.map(({ role, content }) => `${role === "user" ? "You" : "Assistant"}:\n${content}`)
		.join("\n\n");
	const file = new Blob([`${conversation.title}\n\n${text}\n`], { type: "text/plain" });
	const url = URL.createObjectURL(file);
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
			body: JSON.stringify({ message }),
		});
		const data = await response.json();
		if (!response.ok) throw new Error(data?.exc || "The assistant could not respond.");
		const reply = data?.message?.reply || "I'm sorry, I couldn't generate a response just now.";
		const action = data?.message?.action || null;
		pending.bubble.classList.remove("typing");
		pending.bubble.innerHTML = formatAssistantReply(reply);
		if (action) {
			pending.contentWrap.appendChild(createActionCard(action));
		}
		addCopyButton(pending.contentWrap, reply);
		addToConversation("ai", reply, action);
	} catch (error) {
		pending.bubble.classList.remove("typing");
		pending.bubble.textContent = "Something went wrong while contacting the assistant. Please try again.";
		addRetryButton(pending.contentWrap, message, conversationId);
		console.error("Chat request failed:", error);
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
	if (!Recognition) {
		messageInput.placeholder = "Voice input is not supported in this browser";
		return;
	}
	const recognition = new Recognition();
	recognition.lang = "en-US";
	recognition.interimResults = true;
	const voiceButton = document.getElementById("voice-button");
	voiceButton.classList.add("recording");
	voiceButton.setAttribute("aria-label", "Listening — stop voice input");
	recognition.onresult = (event) => {
		messageInput.value = Array.from(event.results)
			.map((result) => result[0].transcript)
			.join("");
		resizeInput();
		messageInput.focus();
	};
	recognition.onerror = () => { messageInput.placeholder = "Couldn't hear that. Please try again."; };
	recognition.onend = () => {
		voiceButton.classList.remove("recording");
		voiceButton.setAttribute("aria-label", "Use voice input");
	};
	recognition.start();
}

function bindSuggestions() {
	document.querySelectorAll(".suggestion").forEach((button) => {
		button.addEventListener("click", () => sendMsg(button.textContent));
	});
}

document.getElementById("chat-form").addEventListener("submit", (event) => {
	event.preventDefault();
	sendMsg();
});
messageInput.addEventListener("input", resizeInput);
messageInput.addEventListener("keydown", (event) => {
	if (event.key === "Enter" && !event.shiftKey) {
		event.preventDefault();
		sendMsg();
	}
});
document.getElementById("voice-button").addEventListener("click", startVoice);
document.getElementById("new-chat").addEventListener("click", startNewConversation);
document.getElementById("export-chat").addEventListener("click", exportConversation);
renderHistory();
bindSuggestions();
})();

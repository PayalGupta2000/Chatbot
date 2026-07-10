const csrf =
    document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");

function scrollToBottom() {
    const box = document.getElementById("chat-box");
    box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
}

/* ---------------- UI ---------------- */

function appendUser(msg) {
    const div = document.createElement("div");
    div.className = "msg user";
    div.innerText = msg;
    document.getElementById("chat-box").appendChild(div);
}

function createAIBox() {
    const div = document.createElement("div");
    div.className = "msg ai";
    document.getElementById("chat-box").appendChild(div);
    return div;
}

/* ---------------- STREAMING ---------------- */

function typeWriter(text, element) {
    const words = text.split(" ");
    let i = 0;
    element.innerHTML = "";

    const interval = setInterval(() => {
        if (i < words.length) {
            element.innerHTML += words[i] + " ";
            i++;
            scrollToBottom();
        } else {
            clearInterval(interval);
            addCopyButton(element, text);
        }
    }, 40);
}

/* ---------------- COPY ---------------- */

function addCopyButton(div, text) {
    const btn = document.createElement("button");
    btn.innerText = "Copy";
    btn.className = "copy-btn";

    btn.onclick = () => {
        navigator.clipboard.writeText(text);
        btn.innerText = "Copied!";
        setTimeout(() => btn.innerText = "Copy", 1500);
    };

    div.appendChild(btn);
}

/* ---------------- CHAT ---------------- */

function sendMsg() {

    let msg = document.getElementById("msg").value;
    if (!msg) return;

    appendUser(msg);
    scrollToBottom();

    document.getElementById("msg").value = "";

    const aiBox = createAIBox();

    fetch("/api/method/chatbot.ai_agent.chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Frappe-CSRF-Token": csrf
        },
        body: JSON.stringify({ message: msg })
    })
    .then(res => res.json())
    .then(data => {

        let reply = data?.message?.reply || "No response";

        typeWriter(reply, aiBox);

        saveHistory(msg, reply);
    });
}

/* ---------------- HISTORY ---------------- */

function saveHistory(msg, reply) {
    let history = document.getElementById("history");

    let div = document.createElement("div");
    div.innerText = msg;

    history.prepend(div);
}

/* ---------------- VOICE INPUT ---------------- */

function startVoice() {
    const recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";

    recognition.onresult = function(event) {
        document.getElementById("msg").value =
            event.results[0][0].transcript;
    };

    recognition.start();
}

/* ---------------- ENTER KEY SEND ---------------- */

document.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        sendMsg();
    }
});
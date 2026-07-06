const STORAGE_KEY = "my_agent_chat_config";

const PRESETS = [
  { label: "출근", message: "출근 처리해줘" },
  { label: "퇴근", message: "퇴근 처리해줘" },
  { label: "출근 상태", message: "오늘 출근했는지 확인해줘" },
  { label: "메이플 실행", message: "메이플 켜줘" },
  { label: "한화오션", message: "한화오션 현재 주가와 수익률 알려줘" },
];

const els = {
  messages: document.getElementById("messages"),
  input: document.getElementById("input"),
  sendBtn: document.getElementById("sendBtn"),
  voiceBtn: document.getElementById("voiceBtn"),
  status: document.getElementById("status"),
  typing: document.getElementById("typing"),
  presets: document.getElementById("presets"),
  settingsBtn: document.getElementById("settingsBtn"),
  settingsDialog: document.getElementById("settingsDialog"),
  settingsForm: document.getElementById("settingsForm"),
  cancelSettings: document.getElementById("cancelSettings"),
  serverUrl: document.getElementById("serverUrl"),
  userId: document.getElementById("userId"),
  userPassword: document.getElementById("userPassword"),
  sessionId: document.getElementById("sessionId"),
  tailscaleHint: document.getElementById("tailscaleHint"),
  fetchTailscaleBtn: document.getElementById("fetchTailscaleBtn"),
  useTailscaleBtn: document.getElementById("useTailscaleBtn"),
};

let ws = null;
let config = loadConfig();
let reconnectTimer = null;
let pendingTailscaleUrl = null;
let isSending = false;

function loadConfig() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function defaultServerUrl() {
  return window.location.origin;
}

function effectiveServerUrl() {
  return (config.serverUrl || defaultServerUrl()).replace(/\/$/, "");
}

function saveConfig() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

function wsUrl() {
  const base = effectiveServerUrl();
  const url = new URL(base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/chat";
  if (config.apiToken) url.searchParams.set("token", config.apiToken);
  if (config.sessionId) url.searchParams.set("session_id", config.sessionId);
  return url.toString();
}

function setStatus(text, connected = false) {
  els.status.textContent = text;
  els.status.classList.toggle("connected", connected);
}

function addBubble(role, text) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  div.textContent = text;
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
}

async function login() {
  const base = effectiveServerUrl();
  const res = await fetch(`${base}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: config.userId,
      password: config.userPassword,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `로그인 실패 (HTTP ${res.status})`);
  }

  const data = await res.json();
  config.apiToken = data.token;
  saveConfig();
  return data.token;
}

function connect() {
  if (!config.apiToken) {
    setStatus("로그인이 필요합니다");
    els.settingsDialog.showModal();
    return;
  }

  if (ws) {
    ws.close();
    ws = null;
  }

  setStatus("연결 중...");
  ws = new WebSocket(wsUrl());

  ws.onopen = () => {
    setStatus("연결됨", true);
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "connected") {
      if (data.session_id) {
        config.sessionId = data.session_id;
        saveConfig();
      }
      addBubble("system", data.message || "연결되었습니다.");
      return;
    }

    if (data.type === "typing") {
      els.typing.classList.toggle("hidden", !data.status);
      if (!data.status) {
        isSending = false;
        setPresetsEnabled(true);
      }
      return;
    }

    if (data.type === "message" && data.role === "assistant") {
      addBubble("assistant", data.message);
      if (data.session_id) {
        config.sessionId = data.session_id;
        saveConfig();
      }
      return;
    }

    if (data.type === "error") {
      addBubble("system", data.message);
      isSending = false;
      setPresetsEnabled(true);
    }
  };

  ws.onclose = () => {
    setStatus("연결 끊김 — 재연결 시도 중...");
    ws = null;
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => {
    setStatus("연결 오류");
  };
}

function setPresetsEnabled(enabled) {
  els.presets.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.disabled = !enabled;
  });
  els.sendBtn.disabled = !enabled;
}

async function sendMessage(forcedText) {
  const text = (forcedText ?? els.input.value).trim();
  if (!text || isSending) return;

  isSending = true;
  setPresetsEnabled(false);

  addBubble("user", text);
  if (!forcedText) els.input.value = "";

  try {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      await sendViaHttp(text);
      return;
    }

    ws.send(
      JSON.stringify({
        message: text,
        session_id: config.sessionId || undefined,
        user_id: config.userId || "mobile_user",
      })
    );
  } finally {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      isSending = false;
      setPresetsEnabled(true);
    }
  }
}

async function sendViaHttp(text) {
  try {
    const res = await fetch(`${effectiveServerUrl()}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(config.apiToken ? { "X-API-Token": config.apiToken } : {}),
      },
      body: JSON.stringify({
        message: text,
        session_id: config.sessionId || undefined,
        user_id: config.userId || "mobile_user",
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    config.sessionId = data.session_id;
    saveConfig();
    addBubble("assistant", data.reply);
  } catch (err) {
    addBubble("system", `전송 실패: ${err.message}`);
  } finally {
    isSending = false;
    setPresetsEnabled(true);
  }
}

function setupPresets() {
  PRESETS.forEach(({ label, message }) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "preset-btn";
    btn.textContent = label;
    btn.addEventListener("click", () => sendMessage(message));
    els.presets.appendChild(btn);
  });
}

function setupVoice() {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    els.voiceBtn.disabled = true;
    els.voiceBtn.title = "이 브라우저는 음성 입력을 지원하지 않습니다";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "ko-KR";
  recognition.interimResults = false;

  els.voiceBtn.addEventListener("click", () => {
    recognition.start();
    setStatus("음성 인식 중...");
  });

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    els.input.value = transcript;
    setStatus("연결됨", ws?.readyState === WebSocket.OPEN);
    sendMessage();
  };

  recognition.onerror = () => {
    setStatus("음성 인식 실패", ws?.readyState === WebSocket.OPEN);
  };
}

els.sendBtn.addEventListener("click", sendMessage);
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

els.settingsBtn.addEventListener("click", () => {
  els.serverUrl.value = config.serverUrl || defaultServerUrl();
  els.userId.value = config.userId || "";
  els.userPassword.value = "";
  els.sessionId.value = config.sessionId || "";
  pendingTailscaleUrl = null;
  els.useTailscaleBtn.classList.add("hidden");
  els.tailscaleHint.classList.add("hidden");
  // Railway/HTTPS 접속 시 서버 주소는 현재 URL 자동 사용
  const onDeployed = window.location.protocol.startsWith("http");
  els.serverUrl.closest("label").style.display = onDeployed ? "none" : "";
  els.settingsDialog.showModal();
});

async function fetchTailscaleInfo(baseUrl) {
  const probe = (baseUrl || els.serverUrl.value || "").trim().replace(/\/$/, "");
  if (!probe || probe.startsWith("https://")) return;

  els.fetchTailscaleBtn.disabled = true;
  showTailscaleHint("Tailscale 정보 조회 중...");

  try {
    const res = await fetch(`${probe}/api/connection-info`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const recommended = data.urls?.recommended || data.urls?.tailscale;

    if (data.tailscale?.connected && recommended) {
      pendingTailscaleUrl = recommended;
      els.useTailscaleBtn.classList.remove("hidden");
      showTailscaleHint(`Tailscale 주소: ${recommended}`);
    } else {
      showTailscaleHint("Tailscale 미연결 — Railway URL 또는 로컬 IP를 사용하세요.");
    }
  } catch (err) {
    showTailscaleHint(`조회 실패: ${err.message}`);
  } finally {
    els.fetchTailscaleBtn.disabled = false;
  }
}

function showTailscaleHint(text) {
  els.tailscaleHint.textContent = text;
  els.tailscaleHint.classList.remove("hidden");
}

els.fetchTailscaleBtn.addEventListener("click", () => fetchTailscaleInfo());
els.useTailscaleBtn.addEventListener("click", () => {
  if (pendingTailscaleUrl) {
    els.serverUrl.value = pendingTailscaleUrl;
    showTailscaleHint("Tailscale 주소 적용됨. 저장 및 연결을 누르세요.");
  }
});

els.cancelSettings.addEventListener("click", () => {
  els.settingsDialog.close();
});

els.settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  config.serverUrl = els.serverUrl.value.trim() || defaultServerUrl();
  config.userId = els.userId.value.trim();
  config.userPassword = els.userPassword.value;
  config.sessionId = els.sessionId.value.trim();

  try {
    setStatus("로그인 중...");
    await login();
    saveConfig();
    els.settingsDialog.close();
    connect();
  } catch (err) {
    showTailscaleHint(err.message);
    setStatus("로그인 실패");
  }
});

setupVoice();
setupPresets();

if (config.apiToken) {
  connect();
} else {
  els.serverUrl.value = config.serverUrl || defaultServerUrl();
  els.settingsDialog.showModal();
}

// 챗봇: 서버의 /chat(로컬 LLM)으로 물품·로봇 상태를 자연어로 묻는 화면
import { api } from "../api.js";
import { h, icon, sidaFace } from "../ui.js";

const SESSION_KEY = "taesula.chatSession";

// 탭을 옮겨 다녀도 대화가 남도록 화면 밖(모듈)에 보관한다
const state = {
  sessionId: loadSessionId(),
  messages: [], // { role: 'user' | 'bot' | 'error', text }
  pending: false,
  startedAt: 0,
};

let view = null; // 지금 화면에 붙어 있는 요소들 (화면을 떠나면 null)

function loadSessionId() {
  let id = null;
  try {
    id = sessionStorage.getItem(SESSION_KEY);
  } catch {
    /* 저장소를 못 쓰면 매번 새 세션 */
  }
  if (!id) {
    id = `app-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    try {
      sessionStorage.setItem(SESSION_KEY, id);
    } catch {
      /* 무시 */
    }
  }
  return id;
}

function newSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* 무시 */
  }
  state.sessionId = loadSessionId();
  state.messages = [];
}

const QUICK = [
  "등록된 물품 목록 보여줘",
  "SIDA 지금 어디 있어?",
  "대기 중인 물품 있어?",
];

export default {
  title: "SIDA 챗봇",

  renderHeader() {
    return [
      h(
        "div",
        { class: "brand" },
        h("div", { class: "brand-mark" }, sidaFace(30)),
        h(
          "div",
          null,
          h("span", { class: "brand-name" }, "SIDA 챗봇"),
          h("span", { class: "brand-sub" }, "물품·로봇 상태를 물어보세요"),
        ),
      ),
      h(
        "button",
        {
          type: "button",
          class: "icon-btn",
          "aria-label": "새 대화 시작",
          onClick: () => {
            if (state.pending) return;
            newSession();
            renderLog();
          },
        },
        icon("refresh", 22),
      ),
    ];
  },

  render(root) {
    const log = h("div", {
      class: "chat-log",
      role: "log",
      "aria-live": "polite",
      "aria-label": "챗봇 대화",
    });
    const quick = h("div", { class: "chat-quick" });
    const input = h("input", {
      class: "input chat-input",
      type: "text",
      id: "chat-input",
      autocomplete: "off",
      placeholder: "SIDA에게 물어보기",
      enterKeyHint: "send",
    });
    const send = h(
      "button",
      { type: "submit", class: "chat-send", "aria-label": "보내기" },
      icon("send", 20, 2.2),
    );
    const form = h(
      "form",
      {
        class: "chat-composer",
        onSubmit: (e) => {
          e.preventDefault();
          ask(input.value);
        },
      },
      h("label", { for: "chat-input", class: "sr-only" }, "메시지 입력"),
      input,
      send,
    );

    for (const q of QUICK)
      quick.append(
        h(
          "button",
          { type: "button", class: "chat-chip", onClick: () => ask(q) },
          q,
        ),
      );

    root.classList.add("chat-screen");
    root.append(log, quick, form);
    view = { log, quick, input, send, timer: null };
    renderLog();
    if (state.pending) startTicker();

    return () => {
      root.classList.remove("chat-screen");
      if (view && view.timer) clearInterval(view.timer);
      view = null;
    };
  },
};

function bubble(m) {
  if (m.role === "user")
    return h(
      "div",
      { class: "msg user" },
      h("div", { class: "bubble" }, m.text),
    );
  return h(
    "div",
    { class: `msg bot${m.role === "error" ? " error" : ""}` },
    h("div", { class: "avatar", "aria-hidden": "true" }, sidaFace(26)),
    h("div", { class: "bubble" }, m.text),
  );
}

function renderLog() {
  if (!view) return;
  const items = [];
  if (!state.messages.length) {
    items.push(
      bubble({
        role: "bot",
        text: "안녕하세요, SIDA예요. 물품 위치나 운송 상태, 로봇 상태를 물어보면 알려드릴게요.",
      }),
    );
  }
  items.push(...state.messages.map(bubble));
  if (state.pending) {
    items.push(
      h(
        "div",
        { class: "msg bot" },
        h("div", { class: "avatar", "aria-hidden": "true" }, sidaFace(26)),
        h(
          "div",
          { class: "bubble typing" },
          h(
            "span",
            { class: "dots", "aria-hidden": "true" },
            h("i"),
            h("i"),
            h("i"),
          ),
          h("span", { class: "wait", id: "chat-wait" }, "생각 중…"),
        ),
      ),
    );
  }
  view.log.replaceChildren(...items);
  view.quick.hidden = state.messages.length > 0 || state.pending;
  view.send.disabled = state.pending;
  view.input.disabled = state.pending;
  requestAnimationFrame(() => window.scrollTo(0, document.body.scrollHeight));
}

function startTicker() {
  if (!view) return;
  if (view.timer) clearInterval(view.timer);
  view.timer = setInterval(() => {
    const el = document.getElementById("chat-wait");
    if (!el) return;
    const sec = Math.floor((Date.now() - state.startedAt) / 1000);
    el.textContent = sec >= 3 ? `생각 중… ${sec}초` : "생각 중…";
  }, 1000);
}

async function ask(text) {
  const message = (text || "").trim();
  if (!message || state.pending) return;
  state.messages.push({ role: "user", text: message });
  state.pending = true;
  state.startedAt = Date.now();
  if (view) view.input.value = "";
  renderLog();
  startTicker();

  try {
    // 라즈베리파이의 소형 LLM은 도구 호출을 여러 번 하면 수십 초가 걸릴 수 있다
    const res = await api.chat(state.sessionId, message);
    state.messages.push({
      role: "bot",
      text: (res && res.reply) || "답변을 받지 못했어요. 다시 물어봐 주세요.",
    });
  } catch (e) {
    const hint =
      e.status === 500
        ? "\n서버에서 챗봇(Ollama)이 실행 중인지 확인해 주세요."
        : "";
    state.messages.push({ role: "error", text: `${e.message}${hint}` });
  } finally {
    state.pending = false;
    if (view && view.timer) {
      clearInterval(view.timer);
      view.timer = null;
    }
    renderLog();
    if (view) view.input.focus();
  }
}

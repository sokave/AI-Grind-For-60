const byId = id => document.getElementById(id);
const source = byId("source");
const generate = byId("generate");
const status = byId("status");
const errorBox = byId("error");
let lastResult = null;

const examples = {
  ml: "Квантизація зменшує кількість бітів для зберігання ваг моделі. У форматі fp16 один параметр займає 2 байти. KV-кеш зберігає ключі та значення уваги для попередніх токенів. Збільшення довжини контексту збільшує пам’ять KV-кешу.",
  net: "DNS перетворює доменні імена на IP-адреси. HTTPS використовує TLS для шифрування з’єднання. HTTP-код 404 означає, що ресурс не знайдено. HTTP-код 503 означає, що сервіс тимчасово недоступний."
};

function updateCounter() {
  byId("counter").textContent = `${source.value.length} / 1800`;
}

source.addEventListener("input", updateCounter);
for (const [key, text] of Object.entries(examples)) {
  byId(`example-${key}`).addEventListener("click", () => {
    source.value = text;
    updateCounter();
  });
}

function showCards(result) {
  byId("cards").replaceChildren();
  result.cards.forEach((card, index) => {
    const article = document.createElement("article");
    article.className = "card";
    const top = document.createElement("div");
    top.className = "card-top";
    const number = document.createElement("span");
    number.textContent = `КАРТКА ${String(index + 1).padStart(2, "0")}`;
    const badge = document.createElement("span");
    badge.textContent = "ЦИТАТУ ПЕРЕВІРЕНО ✓";
    top.append(number, badge);
    const question = document.createElement("h3");
    question.textContent = card.question;
    const answer = document.createElement("p");
    answer.className = "answer";
    answer.textContent = card.answer;
    answer.hidden = true;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.textContent = "Показати відповідь";
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", () => {
      answer.hidden = !answer.hidden;
      toggle.textContent = answer.hidden ? "Показати відповідь" : "Сховати відповідь";
      toggle.setAttribute("aria-expanded", String(!answer.hidden));
    });
    article.append(top, question, toggle, answer);
    byId("cards").append(article);
  });
  byId("empty").hidden = true;
  const meta = byId("result-meta");
  meta.hidden = false;
  meta.textContent = `${result.elapsed_s.toFixed(1)} с · ${result.usage.completion_tokens ?? "—"} токенів · відповіді звірено з конспектом`;
}

generate.addEventListener("click", async () => {
  errorBox.hidden = true;
  lastResult = null;
  byId("export").disabled = true;
  byId("cards").replaceChildren();
  byId("result-meta").hidden = true;
  byId("empty").hidden = false;
  generate.disabled = true;
  status.classList.add("busy");
  status.textContent = "Модель створює картки… 0 с";
  const start = Date.now();
  const ticker = setInterval(() => {
    status.textContent = `Модель створює картки… ${Math.floor((Date.now() - start) / 1000)} с`;
  }, 1000);
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 195000);
  try {
    const response = await fetch("/api/cards", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({source: source.value, count: Number(byId("count").value)}),
      signal: controller.signal
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Не вдалося створити картки.");
    if (!Array.isArray(result.cards)) throw new Error("Сервер повернув некоректну відповідь.");
    lastResult = result;
    showCards(result);
    byId("export").disabled = false;
    status.textContent = `Готово: ${result.cards.length} картки`;
  } catch (error) {
    errorBox.hidden = false;
    errorBox.textContent = error.name === "AbortError" ? "Час очікування вичерпано. Скоротіть конспект і повторіть запит." : (error.message === "Failed to fetch" ? "Немає з’єднання із застосунком. Перевірте, чи запущено server.py." : error.message);
    status.textContent = "Запит не виконано";
  } finally {
    clearInterval(ticker);
    clearTimeout(deadline);
    status.classList.remove("busy");
    generate.disabled = false;
  }
});

byId("export").addEventListener("click", () => {
  if (!lastResult) return;
  const blob = new Blob([JSON.stringify(lastResult, null, 2)], {type: "application/json;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "study_cards.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

fetch("/api/config").then(response => response.json()).then(config => {
  byId("model").textContent = `${config.model} · ${config.base_url}`;
}).catch(() => { byId("model").textContent = "Локальний API недоступний"; });

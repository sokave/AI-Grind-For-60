import { buildPrompt, inspectResponse, sections, toMarkdown } from "./core.mjs";

const byId = (id) => document.getElementById(id);
const source = byId("source");
const response = byId("response");
const prompt = byId("prompt");
const promptPanel = byId("prompt-panel");
const sourceStatus = byId("source-status");
const resultStatus = byId("result-status");
const download = byId("download");
const preview = byId("preview");
const emptyPreview = preview.firstElementChild;
let checklist = null;

function setStatus(element, message = "", state = "") {
  element.textContent = message;
  element.dataset.state = state;
}

function clearResult() {
  checklist = null;
  download.disabled = true;
  preview.replaceChildren(emptyPreview);
  setStatus(resultStatus);
}

function clearPrompt() {
  prompt.value = "";
  promptPanel.hidden = true;
  promptPanel.open = false;
  setStatus(byId("copy-status"));
  setStatus(sourceStatus);
  clearResult();
}

source.addEventListener("input", clearPrompt);
response.addEventListener("input", clearResult);

byId("assignment-file").addEventListener("change", async (event) => {
  const picker = event.currentTarget;
  const file = picker.files[0];
  if (!file) return;
  const previousSource = source.value;
  try {
    const content = await file.text();
    if (picker.files[0] !== file || source.value !== previousSource) return;
    source.value = content;
    clearPrompt();
    setStatus(sourceStatus, `Відкрито ${file.name}`, "ok");
  } catch {
    setStatus(sourceStatus, "Вставте текст вручну або відкрийте файл ще раз.", "error");
  } finally {
    if (picker.files[0] === file) picker.value = "";
  }
});

byId("prepare").addEventListener("click", () => {
  if (!source.value.trim()) {
    setStatus(sourceStatus, "Додайте умову завдання.", "error");
    source.focus();
    return;
  }
  prompt.value = buildPrompt(source.value);
  promptPanel.hidden = false;
  promptPanel.open = true;
  setStatus(sourceStatus, "Запит готовий");
});

byId("copy").addEventListener("click", async () => {
  const status = byId("copy-status");
  try {
    await navigator.clipboard.writeText(prompt.value);
    setStatus(status, "Скопійовано", "ok");
  } catch {
    prompt.focus();
    prompt.select();
    setStatus(status, "Скопіюйте виділений текст вручну.", "error");
  }
});

function element(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}

function render(checklistToRender, missingQuotes) {
  const content = document.createDocumentFragment();
  content.append(element("h3", checklistToRender.title, "checklist-title"));
  const note = missingQuotes
    ? "Виправте або приберіть позначені пункти в JSON перед завантаженням."
    : "Звірте зміст і повноту пунктів з умовою. Цитати відкриваються під кожним пунктом.";
  content.append(element("p", note, missingQuotes ? "hint warning" : "hint"));

  for (const [key, label] of sections) {
    const items = checklistToRender[key];
    if (!items.length && key !== "deadlines") continue;

    const group = element("section", "", "result-group");
    group.dataset.section = key;
    group.append(element("h4", label));
    if (!items.length) group.append(element("p", "У тексті дедлайн не вказано.", "hint"));
    const list = element("ul", "", "result-list");
    for (const item of items) {
      const row = element("li", "", item.matched ? "" : "unmatched");
      if (key === "deadlines") {
        row.append(element("p", item.text, "deadline"));
      } else {
        const label = element("label", "", "check-item");
        const checkbox = element("input", "");
        checkbox.type = "checkbox";
        checkbox.addEventListener("change", () => { item.checked = checkbox.checked; });
        label.append(checkbox, element("span", item.text));
        row.append(label);
      }
      const citation = element("details", "", "citation");
      citation.append(
        element("summary", item.matched ? "Цитата з умови" : "Цитату не знайдено"),
        element("blockquote", item.quote),
      );
      citation.open = !item.matched;
      row.append(citation);
      list.append(row);
    }
    if (items.length) group.append(list);
    content.append(group);
  }
  preview.replaceChildren(content);
}

byId("assemble").addEventListener("click", () => {
  clearResult();
  try {
    const result = inspectResponse(source.value, response.value);
    checklist = result.checklist;
    render(checklist, result.missingQuotes);
    download.disabled = Boolean(result.missingQuotes);
    if (result.missingQuotes) {
      setStatus(resultStatus, `Цитат не знайдено: ${result.missingQuotes} із ${result.itemCount}`, "error");
    } else {
      setStatus(resultStatus, `Цитати знайдено: ${result.itemCount} із ${result.itemCount}`, "ok");
    }
  } catch (error) {
    setStatus(resultStatus, error.message, "error");
  }
});

download.addEventListener("click", () => {
  if (!checklist || download.disabled) return;
  const url = URL.createObjectURL(new Blob([toMarkdown(checklist)], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "checklist.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

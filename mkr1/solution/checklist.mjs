import { readFileSync, writeFileSync } from "node:fs";
import { buildPrompt, inspectResponse, sections, toMarkdown } from "./core.mjs";

const usage = `Команди:
  node solution/checklist.mjs prompt <умова.md>
  node solution/checklist.mjs export <умова.md> <відповідь.json> [чекліст.md]`;

const args = process.argv.slice(2);
const [command, sourcePath, responsePath, outputPath] = args;

try {
  if (args.length === 1 && command === "--help") {
    console.log(usage);
  } else if (command === "prompt" && args.length === 2) {
    const source = readFileSync(sourcePath, "utf8");
    if (!source.trim()) throw new Error("Додайте текст умови у вхідний файл.");
    console.log(buildPrompt(source));
  } else if (command === "export" && (args.length === 3 || args.length === 4)) {
    const source = readFileSync(sourcePath, "utf8");
    const response = readFileSync(responsePath, "utf8");
    const { checklist, itemCount, missingQuotes } = inspectResponse(source, response);

    if (missingQuotes) {
      console.error(`Цитат не знайдено: ${missingQuotes} із ${itemCount}.`);
      for (const [key, label] of sections) {
        for (const item of checklist[key].filter((entry) => !entry.matched)) {
          console.error(`  ${label} — ${item.text}`);
        }
      }
      throw new Error("Звірте позначені пункти з умовою, виправте відповідь і повторіть експорт.");
    }

    const markdown = toMarkdown(checklist);
    if (outputPath) {
      writeFileSync(outputPath, markdown, { encoding: "utf8", flag: "wx" });
    } else {
      process.stdout.write(markdown);
    }
    console.error(`Цитати знайдено: ${itemCount} із ${itemCount}. Звірте зміст пунктів з умовою.`);
    if (outputPath) console.error(`Збережено ${outputPath}`);
  } else {
    console.error(usage);
    process.exitCode = 1;
  }
} catch (error) {
  if (error.code === "EEXIST") {
    console.error(`Файл ${outputPath} вже існує. Вкажіть іншу назву.`);
  } else {
    console.error(error.message);
  }
  process.exitCode = 1;
}

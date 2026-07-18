import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function walk(directory: string, extensions: string[]): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) files.push(...walk(path, extensions));
    else if (extensions.some(extension => path.endsWith(extension))) files.push(path);
  }
  return files;
}

const styleFiles = walk("src/styles", [".css"]);
const definedTokens = new Set<string>();
for (const file of styleFiles) {
  for (const match of readFileSync(file, "utf8").matchAll(/--[a-z0-9-]+(?=\s*:)/g)) definedTokens.add(match[0]);
}

describe("ink design tokens", () => {
  it("resolves every referenced CSS variable", () => {
    const sources = walk("src", [".ts", ".tsx", ".css"]).filter(file => !file.endsWith("tokens.test.ts"));
    const missing: string[] = [];
    for (const file of sources) {
      for (const match of readFileSync(file, "utf8").matchAll(/var\(\s*(--[a-z0-9-]+)/g)) {
        if (!definedTokens.has(match[1])) missing.push(`${file}: ${match[1]}`);
      }
    }
    expect(missing).toEqual([]);
  });

  it("keeps hardcoded colors out of feature and component code", () => {
    const offenders: string[] = [];
    for (const file of [...walk("src/features", [".ts", ".tsx", ".css"]), ...walk("src/components", [".ts", ".tsx", ".css"])]) {
      const matches = readFileSync(file, "utf8").match(/#[0-9a-fA-F]{3,8}\b|rgb\(/g);
      if (matches) offenders.push(`${file}: ${matches.join(", ")}`);
    }
    expect(offenders).toEqual([]);
  });
});

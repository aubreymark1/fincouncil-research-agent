import assert from "node:assert/strict";
import { getInitialTheme, nextTheme } from "../src/theme.ts";

const storage = (value: string | null) => ({
  getItem: (_key: string) => value,
});

assert.equal(nextTheme("dark"), "light");
assert.equal(nextTheme("light"), "dark");
assert.equal(getInitialTheme(storage("light"), false), "light");
assert.equal(getInitialTheme(storage(null), true), "light");
assert.equal(getInitialTheme(storage(null), false), "dark");

console.log("theme behavior tests passed");

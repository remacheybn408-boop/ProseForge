import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// vitest runs with globals disabled, so @testing-library/react's automatic
// cleanup never registers; without it every render accumulates in jsdom and
// later tests in the same file see duplicate elements.
afterEach(() => {
  cleanup();
});

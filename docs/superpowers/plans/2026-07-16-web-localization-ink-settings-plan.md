# Web 本地化、水墨视觉与设置页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 ProseForge Web 改为默认简体中文、可切换英文的水墨书卷界面，并让设置页适合普通用户使用。

**Architecture:** 在 `apps/web/src/lib/i18n.ts` 提供轻量字典、语言状态和翻译函数；`App` 持有语言状态并将翻译函数传给页面组件。CSS 通过新的设计令牌统一宣纸、墨色和朱砂色，不改变 API 或业务数据结构。设置页仍调用现有 credential/profile API，只调整文案、分组、状态和帮助说明。

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, CSS, Docker Compose。

## Global Constraints

- 默认语言必须是 `zh-CN`，语言选择位于左侧导航底部，并保存到 `localStorage`。
- 只翻译界面文案，不翻译用户项目、章节、提示词和模型返回内容。
- 不引入大型国际化依赖、外部图片资源或 API 数据结构变更。
- 所有测试、构建和运行验证必须在 Docker 容器内完成。

---

### Task 1: Add the language dictionary and persistence

**Files:**
- Create: `apps/web/src/lib/i18n.ts`
- Test: `apps/web/src/lib/i18n.test.ts`

**Interfaces:**
- Produces `Language = "zh-CN" | "en-US"`, `defaultLanguage`, `loadLanguage()`, `saveLanguage()`, and `createTranslator(language)`.
- `createTranslator` returns `(key: TranslationKey) => string` and falls back to the key when a translation is missing.

- [ ] **Step 1: Write failing tests** for default language, persisted language, and representative Chinese/English translations.
- [ ] **Step 2: Run `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test pnpm vitest run src/lib/i18n.test.ts` and confirm failure.**
- [ ] **Step 3: Implement the typed dictionary and localStorage helpers.** Use `proseforge.web.language` as the storage key and treat invalid stored values as `zh-CN`.
- [ ] **Step 4: Rerun the focused Docker test and confirm it passes.**

### Task 2: Wire language switching through the application

**Files:**
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/app.test.tsx`

**Interfaces:**
- `App` owns language state and passes `t` to navigation and view components.
- The left rail renders buttons labeled `中文` and `English`; clicking updates state and persistence without changing user content.

- [ ] **Step 1: Add a failing UI test** that renders the app with a mocked authenticated project, checks Chinese default navigation, clicks `English`, and checks persistence.
- [ ] **Step 2: Run the focused Web test in Docker and confirm the new assertions fail.**
- [ ] **Step 3: Replace hard-coded user-facing labels in `Login`, `Projects`, `Studio`, `OutlineView`, `ContextView`, `WorkflowView`, `SettingsView`, inspector, and navigation with dictionary keys.** Keep API values and user-entered text unchanged.
- [ ] **Step 4: Add the language switcher to the rail bottom and call `saveLanguage` on change.**
- [ ] **Step 5: Run all Web unit tests in Docker and confirm they pass.**

### Task 3: Apply the ink-style visual system

**Files:**
- Modify: `apps/web/src/styles/tokens.css`
- Modify: `apps/web/src/styles/views.css`

**Interfaces:**
- Preserve existing class names and component layout contracts.
- Add design tokens for paper, ink, secondary ink, vermilion, wash, border, and shadow; use CSS-only gradients for subtle ink wash.

- [ ] **Step 1: Add visual regression-oriented assertions** to the Web test for the paper background, vermilion primary action, and visible language controls.
- [ ] **Step 2: Implement the tokens and styles.** Use high-contrast text, serif headings/editor text, reduced card borders, ink-wash backgrounds, seal-like active navigation, and responsive language controls.
- [ ] **Step 3: Run Web tests and Vite build in Docker.**
- [ ] **Step 4: Start the production Compose stack in Docker and manually inspect `/` at `http://localhost:3000`.**

### Task 4: Rebuild Settings for ordinary users

**Files:**
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/styles/views.css`
- Modify: `apps/web/src/app.test.tsx`

**Interfaces:**
- Keep `saveCredential`, `probeProvider`, and `saveModelProfile` calls unchanged.
- Display translated sections for model service connection, writing roles, and connection status.

- [ ] **Step 1: Add failing UI assertions** for Chinese field labels, explanatory text, masked credential status, and the translated “测试连接” action.
- [ ] **Step 2: Implement the Settings layout.** Rename labels to `服务商`, `API 密钥`, `接口地址（可选）`, `写作模型`, `审校模型`, and `模型名称 / Model ID`; add examples and short help text; show status labels `已连接`, `未连接`, `检查失败` based on probe state.
- [ ] **Step 3: Keep secrets out of rendered values and clear the API key after successful save.**
- [ ] **Step 4: Run focused Settings tests in Docker and confirm they pass.**

### Task 5: Full Docker verification and handoff

**Files:**
- Modify: `artifacts/WEB_V1_INCREMENTAL_VALIDATION.md`

- [ ] **Step 1: Run `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test`.** Expected: all Web tests pass and Vite build succeeds.
- [ ] **Step 2: Run `docker compose -f compose.yaml -f compose.test.yaml run --rm e2e`.** Expected: ordinary-user smoke flow passes.
- [ ] **Step 3: Run `docker compose up -d --build` and `docker compose ps`.** Expected: Web, API, Worker, Scheduler, PostgreSQL, Redis, and Provider Mock are healthy.
- [ ] **Step 4: Record the final Docker results in `artifacts/WEB_V1_INCREMENTAL_VALIDATION.md`.**
- [ ] **Step 5: Run `git diff --check`, review the diff, commit the implementation, and push `master` only after verification passes.**


import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type Language = "zh-CN" | "en-US";
export const defaultLanguage: Language = "zh-CN";
export const languageStorageKey = "proseforge.web.language";

const messages = {
  "zh-CN": {
    appName: "ProseForge", currentProject: "当前项目", projects: "项目", writingStudio: "写作工作台", outlineIntake: "大纲导入", context: "故事记忆", workflow: "工作流", settings: "设置", allProjects: "全部项目", projectStatus: "项目状态", readyToContinue: "可以继续创作", dockerSaved: "内容保存在 Docker 工作空间中。", notStarted: "尚未开始", openWorkflow: "查看工作流", apiOnline: "API：在线", apiOffline: "API：离线", yourWorkspaces: "你的创作空间", chooseProject: "选择项目继续写作，或从故事大纲开始创建项目。", writingProject: "写作项目", active: "进行中", open: "打开", noProjects: "还没有项目。创建你的第一个写作空间吧。", newProject: "新建项目", cancel: "取消", projectTitle: "项目名称", projectTitlePlaceholder: "例如：月光档案", urlSlug: "项目标识（可选）", urlSlugPlaceholder: "例如：moonlit-archive", createProject: "创建项目", chapters: "章节", readyToWrite: "可以开始写作", importOutlineToCreate: "导入大纲后会自动创建章节", loadingChapters: "正在加载章节…", saveVersion: "保存版本", downloadMarkdown: "下载 Markdown", writingCompanion: "写作助手", modelProfile: "模型配置", askCompanion: "告诉助手你想修改的内容…", send: "发送", forkBranch: "创建分支", waitingForWorker: "等待 Worker 处理…", outlineHero: "从故事想法开始", outlineIntro: "先保存大纲，再只询问仍然缺少的信息。", outlineTitle: "大纲名称", outlineTitlePlaceholder: "例如：月光档案", outlineNotes: "故事大纲或创作笔记", outlineNotesPlaceholder: "写下故事背景、人物和结局…", importAnalyze: "导入并分析", status: "状态", readyConfirm: "可以确认", answerMissing: "补充缺少的信息", saveAnswer: "保存回答", confirmWorkflow: "确认并创建工作流", outlineFailed: "大纲导入失败，请检查内容后重试。", contextHero: "故事记忆库", contextIntro: "固定重要事实，让写作助手在后续章节中保持一致。", addMemory: "添加故事记忆", addMemoryPlaceholder: "例如：Mira 害怕深水", addContext: "添加记忆", pinned: "已置顶", pin: "置顶", unpin: "取消置顶", workflowHero: "章节写作工作流", outlineConfirmed: "大纲已确认", savedToPostgres: "已保存到 PostgreSQL", draftChapter: "生成章节初稿", reviewCommit: "审校并提交", waiting: "等待中", pause: "暂停", resume: "继续", retry: "重试", modelSettings: "模型设置", providerConnections: "模型服务连接", providerIntro: "配置一次即可使用。密钥只保存在服务端，不会回显到浏览器。", provider: "服务商", apiKey: "API 密钥", apiKeyHelp: "服务商提供的访问密钥，只用于调用模型。", baseUrl: "接口地址（可选）", baseUrlHelp: "使用兼容接口或本地模型时填写，例如 http://localhost:11434/v1。", saveProvider: "保存模型服务", secretsNeverPrefilled: "为保护安全，密钥不会自动填回。", configured: "已配置", connected: "已连接", notConnected: "未连接", checkFailed: "检查失败", testConnection: "测试连接", writerEditor: "写作角色", writerEditorIntro: "为写作和审校分别选择模型配置。", writerModel: "写作模型", editorModel: "审校模型", profileName: "配置名称", profileNamePlaceholder: "例如：中文长篇写作", modelId: "模型名称 / Model ID", modelIdHelp: "填写服务商提供的模型标识，例如 gpt-4.1-mini。", saveProfile: "保存模型配置", firstRun: "首次使用？创建所有者账户", alreadyAccount: "我已经有账户", signIn: "登录", createOwner: "创建所有者账户", signInTitle: "登录你的写作空间", authIntro: "项目、草稿、故事记忆和模型设置都会保存在 Docker 工作空间中。", languageChinese: "中文", languageEnglish: "English", connectionChecking: "正在检查", connectionOnline: "在线", connectionOffline: "离线", savedVersion: "已保存版本", loadedVersion: "已加载版本", unableLoad: "暂时无法加载内容", genericError: "操作失败，请稍后重试。"
  },
  "en-US": {
    appName: "ProseForge", currentProject: "CURRENT PROJECT", projects: "Projects", writingStudio: "Writing Studio", outlineIntake: "Outline intake", context: "Story memory", workflow: "Workflow", settings: "Settings", allProjects: "All projects", projectStatus: "Project status", readyToContinue: "Ready to continue", dockerSaved: "Everything is saved in your Docker-backed workspace.", notStarted: "Not started", openWorkflow: "Open workflow", apiOnline: "API: Online", apiOffline: "API: Offline", yourWorkspaces: "YOUR WORKSPACES", chooseProject: "Choose a project to continue writing, or start a new one from an outline.", writingProject: "Writing project", active: "ACTIVE", open: "Open", noProjects: "No projects yet. Create your first writing space below.", newProject: "New project", cancel: "Cancel", projectTitle: "Project title", projectTitlePlaceholder: "The Moonlit Archive", urlSlug: "Project slug (optional)", urlSlugPlaceholder: "moonlit-archive", createProject: "Create project", chapters: "Chapters", readyToWrite: "Ready to write", importOutlineToCreate: "Import an outline to create chapters", loadingChapters: "Loading chapters…", saveVersion: "Save version", downloadMarkdown: "Download Markdown", writingCompanion: "Writing companion", modelProfile: "Model profile", askCompanion: "Ask your companion…", send: "Send", forkBranch: "Fork branch", waitingForWorker: "Waiting for the worker…", outlineHero: "Start from your story idea", outlineIntro: "ProseForge saves the outline before asking only the questions it still needs.", outlineTitle: "Outline title", outlineTitlePlaceholder: "The Moonlit Archive", outlineNotes: "Outline or story notes", outlineNotesPlaceholder: "Paste your outline, characters and ending…", importAnalyze: "Import and analyze", status: "Status", readyConfirm: "Ready to confirm", answerMissing: "Answer the missing requirement", saveAnswer: "Save answer", confirmWorkflow: "Confirm and create workflow", outlineFailed: "Outline import failed. Check the content and try again.", contextHero: "Story memory", contextIntro: "Pin important facts so the writing companion keeps later chapters consistent.", addMemory: "Add a story memory", addMemoryPlaceholder: "Mira is afraid of deep water", addContext: "Add memory", pinned: "Pinned", pin: "Pin", unpin: "Unpin", workflowHero: "Chapter workflow", outlineConfirmed: "Outline confirmed", savedToPostgres: "Saved to PostgreSQL", draftChapter: "Draft chapter", reviewCommit: "Review and commit", waiting: "Waiting", pause: "Pause", resume: "Resume", retry: "Retry", modelSettings: "MODEL SETTINGS", providerConnections: "Model service connections", providerIntro: "Connect a provider once. Secrets stay on the server and are never rendered back into the browser.", provider: "Provider", apiKey: "API key", apiKeyHelp: "The access key supplied by your model provider.", baseUrl: "Endpoint URL (optional)", baseUrlHelp: "Use this for compatible endpoints or local models, for example http://localhost:11434/v1.", saveProvider: "Save model service", secretsNeverPrefilled: "Secrets are never prefilled.", configured: "Configured", connected: "Connected", notConnected: "Not connected", checkFailed: "Check failed", testConnection: "Test connection", writerEditor: "Writing roles", writerEditorIntro: "Choose separate model profiles for drafting and review.", writerModel: "Writing model", editorModel: "Editor model", profileName: "Profile name", profileNamePlaceholder: "Fast long-form writer", modelId: "Model name / Model ID", modelIdHelp: "Use the identifier supplied by the provider, such as gpt-4.1-mini.", saveProfile: "Save model profile", firstRun: "First run? Create the owner account", alreadyAccount: "I already have an account", signIn: "Sign in", createOwner: "Create your owner account", signInTitle: "Sign in to your writing space", authIntro: "Your projects, drafts, story memory and provider settings stay in your Docker-backed workspace.", languageChinese: "中文", languageEnglish: "English", connectionChecking: "Checking", connectionOnline: "Online", connectionOffline: "Offline", savedVersion: "Saved version", loadedVersion: "Loaded version", unableLoad: "Unable to load content", genericError: "Something went wrong. Please try again."
  }
} as const;

export type TranslationKey = keyof typeof messages["zh-CN"];
export type Translator = (key: TranslationKey) => string;

export function loadLanguage(): Language {
  if (typeof window === "undefined") return defaultLanguage;
  const value = window.localStorage.getItem(languageStorageKey);
  return value === "en-US" || value === "zh-CN" ? value : defaultLanguage;
}

export function saveLanguage(language: Language): void {
  if (typeof window !== "undefined") window.localStorage.setItem(languageStorageKey, language);
}

export function createTranslator(language: Language): Translator {
  return key => messages[language][key] ?? messages[defaultLanguage][key] ?? key;
}

type LanguageContextValue = { language: Language; setLanguage: (language: Language) => void; t: Translator };
const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(loadLanguage);
  const setLanguage = (next: Language) => { saveLanguage(next); setLanguageState(next); };
  const value = useMemo(() => ({ language, setLanguage, t: createTranslator(language) }), [language]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageContextValue {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useLanguage must be used inside LanguageProvider");
  return value;
}

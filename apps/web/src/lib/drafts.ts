export type ChatDraftKey = {
  conversationId: string;
  branchId: string;
  draftType: "chat";
};

export type ChapterDraftKey = {
  projectId: string;
  chapterId: string;
  draftType: "chapter";
};

export type DraftKey = ChatDraftKey | ChapterDraftKey;

type DraftRecord = DraftKey & { key: string; content: string; updatedAt: number };

const DATABASE = "proseforge-drafts";
const STORE = "drafts";

function keyOf(key: DraftKey) {
  if (key.draftType === "chapter") return `chapter:${key.projectId}:${key.chapterId}`;
  return `${key.conversationId}:${key.branchId}:${key.draftType}`;
}

function openDatabase(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE, { keyPath: "key" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveDraft(key: DraftKey, content: string): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE, "readwrite");
    const store = transaction.objectStore(STORE);
    const request = content ? store.put({ key: keyOf(key), ...key, content, updatedAt: Date.now() }) : store.delete(keyOf(key));
    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  database.close();
}

export async function loadDraft(key: DraftKey): Promise<string> {
  const database = await openDatabase();
  if (!database) return "";
  return new Promise((resolve, reject) => {
    const request = database.transaction(STORE, "readonly").objectStore(STORE).get(keyOf(key));
    request.onsuccess = () => { database.close(); resolve((request.result as DraftRecord | undefined)?.content ?? ""); };
    request.onerror = () => { database.close(); reject(request.error); };
  });
}

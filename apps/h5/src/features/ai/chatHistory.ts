import {
  asRecord,
  asTrimmedString,
  readLocal,
  writeLocal,
  type LocalStoreDefinition
} from "../../storage/localStore";

/** 一次和 AI 闺蜜的对话，落在本机。 */
export type ChatRecord = {
  id: string;
  /** ISO 日期，列表里显示成 MM-DD。 */
  date: string;
  /** 这次聊的主题，取第一句话。 */
  theme: string;
  /** 最后一句 AI 说的话。 */
  last: string;
  /** 这次最终存进衣橱的那套；没存就是 null。 */
  outfitTitle: string | null;
  outfitLookId: string | null;
};

/**
 * 只留最近这些条。对话记录是给人回看的，不是日志；
 * 无上限增长迟早会把 localStorage 撑爆，而配额一满，
 * 身材资料和形象照会跟着写不进去。
 */
export const MAX_CHAT_RECORDS = 20;

const MAX_TEXT = 120;

export const chatHistoryStore: LocalStoreDefinition<ChatRecord[]> = {
  key: "stylecapture:ai-chat-history:v1",
  fallback: () => [],
  parse: (raw) => {
    if (!Array.isArray(raw)) return null;
    const records: ChatRecord[] = [];
    for (const entry of raw) {
      const record = asRecord(entry);
      if (!record) continue;
      const id = asTrimmedString(record.id, 64);
      const date = asTrimmedString(record.date, 32);
      const theme = asTrimmedString(record.theme, MAX_TEXT);
      if (!id || !date || !theme) continue;
      records.push({
        id,
        date,
        theme,
        last: asTrimmedString(record.last, MAX_TEXT) ?? "",
        outfitTitle: asTrimmedString(record.outfitTitle, MAX_TEXT),
        outfitLookId: asTrimmedString(record.outfitLookId, 64)
      });
    }
    return records.slice(0, MAX_CHAT_RECORDS);
  }
};

export function readChatHistory(): ChatRecord[] {
  return readLocal(chatHistoryStore);
}

/**
 * 写入一条对话，最新的排在最前。
 *
 * 同一次对话会被反复保存（每多聊一轮、存了穿搭都要更新），所以按 id 覆盖，
 * 而不是每次追加一条新的——否则一次对话会在列表里出现七八遍。
 */
export function upsertChatRecord(
  history: readonly ChatRecord[],
  record: ChatRecord
): ChatRecord[] {
  const rest = history.filter((entry) => entry.id !== record.id);
  return [record, ...rest].slice(0, MAX_CHAT_RECORDS);
}

export function saveChatHistory(records: readonly ChatRecord[]) {
  return writeLocal(chatHistoryStore, records.slice(0, MAX_CHAT_RECORDS));
}

/** 列表里显示成 07-21 这种。日期存不下来时原样返回，不编一个。 */
export function displayDate(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  const month = `${parsed.getMonth() + 1}`.padStart(2, "0");
  const day = `${parsed.getDate()}`.padStart(2, "0");
  return `${month}-${day}`;
}

import {
  MAX_CHAT_RECORDS,
  chatHistoryStore,
  displayDate,
  readChatHistory,
  saveChatHistory,
  upsertChatRecord,
  type ChatRecord
} from "../src/features/ai/chatHistory";

function record(id: string, theme = "通勤"): ChatRecord {
  return {
    id,
    date: "2026-07-21T09:00:00.000Z",
    theme,
    last: "那就用棕黄这套",
    outfitTitle: null,
    outfitLookId: null,
    messages: [{ role: "user", text: theme }]
  };
}

describe("ai chat history", () => {
  beforeEach(() => window.localStorage.clear());

  it("keeps one entry per conversation instead of one per round", () => {
    // 多聊几轮会反复保存同一次对话；按 id 覆盖，否则一次对话会刷屏。
    let history = upsertChatRecord([], record("c1", "通勤"));
    history = upsertChatRecord(history, {
      ...record("c1", "通勤"),
      last: "换成平底鞋更好走"
    });
    expect(history).toHaveLength(1);
    expect(history[0].last).toBe("换成平底鞋更好走");
  });

  it("puts the newest conversation first", () => {
    let history = upsertChatRecord([], record("old", "上周"));
    history = upsertChatRecord(history, record("new", "今天"));
    expect(history.map((entry) => entry.theme)).toEqual(["今天", "上周"]);
  });

  it("stops growing so it cannot squeeze out the profile and photos", () => {
    let history: ChatRecord[] = [];
    for (let index = 0; index < MAX_CHAT_RECORDS + 6; index += 1) {
      history = upsertChatRecord(history, record(`c${index}`));
    }
    expect(history).toHaveLength(MAX_CHAT_RECORDS);
  });

  it("survives a hand-corrupted store instead of blocking startup", () => {
    window.localStorage.setItem(chatHistoryStore.key, "{ not json");
    expect(readChatHistory()).toEqual([]);
  });

  it("drops entries that lost the fields the list needs", () => {
    window.localStorage.setItem(
      chatHistoryStore.key,
      JSON.stringify([{ id: "c1" }, record("c2")])
    );
    const read = readChatHistory();
    expect(read.map((entry) => entry.id)).toEqual(["c2"]);
  });

  it("round-trips through storage", () => {
    saveChatHistory([record("c1", "面试")]);
    expect(readChatHistory()[0].theme).toBe("面试");
  });

  it("shows the date the way the list does, and does not invent one", () => {
    expect(displayDate("2026-07-21T09:00:00.000Z")).toMatch(/^\d{2}-\d{2}$/);
    expect(displayDate("说不清")).toBe("说不清");
  });

  it("keeps what was said, so a conversation without a saved outfit is still worth opening", () => {
    // 只留主题和最后一句的话，点进去是空的，这个功能就没意义了。
    window.localStorage.setItem(
      chatHistoryStore.key,
      JSON.stringify([
        {
          ...record("c1"),
          messages: [
            { role: "user", text: "周末约会" },
            { role: "ai", text: "配色柔和一点更好" }
          ]
        }
      ])
    );
    expect(readChatHistory()[0].messages).toEqual([
      { role: "user", text: "周末约会" },
      { role: "ai", text: "配色柔和一点更好" }
    ]);
  });

  it("survives a record whose messages were mangled", () => {
    window.localStorage.setItem(
      chatHistoryStore.key,
      JSON.stringify([{ ...record("c1"), messages: [null, 7, { text: "在" }] }])
    );
    // 坏掉的几句丢掉，整条记录还留着——不该因为一句话读不出来就整条消失。
    expect(readChatHistory()[0].messages).toEqual([{ role: "user", text: "在" }]);
  });

  it("never loses the saved outfit just because the chat went on", () => {
    // 存过的搭配是这条记录里最有价值的东西。从前每写一轮都把它抹成 null，
    // 于是点对话记录只能进到新对话。
    const saved: ChatRecord = {
      ...record("c1"),
      outfitTitle: "棕黄复古通勤",
      outfitLookId: "look-1"
    };
    let history = upsertChatRecord([], saved);
    history = upsertChatRecord(history, {
      ...saved,
      outfitTitle: saved.outfitTitle,
      outfitLookId: saved.outfitLookId,
      last: "又聊了一句"
    });
    expect(history[0].outfitLookId).toBe("look-1");
    expect(history[0].last).toBe("又聊了一句");
  });
});

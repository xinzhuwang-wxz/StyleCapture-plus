/**
 * Preset guests for the party.
 *
 * These are authored characters, not other users and not live presence. Every
 * line is written here in advance; nothing is generated at runtime and nothing
 * claims to be a real person. The UI labels them accordingly.
 *
 * One persona per art set: the pose pack ships four characters, so the party has
 * four guests and nobody appears twice.
 */

export type DialogueLine = {
  speaker: "guest" | "player";
  text: string;
};

export type GuestPersona = {
  id: string;
  name: string;
  /** Which Look this guest wears; one persona per pose set. */
  lookId: string;
  /** One line of self-description shown when tapped. */
  bio: string;
  /** Idle chatter, spoken while wandering. */
  smallTalk: readonly string[];
  /** Fired at the performer during the runway. */
  runwayCheers: readonly string[];
  /** Played as a back-and-forth when the player walks over to say hello. */
  conversation: readonly DialogueLine[];
  /** Why this person is at each location, keyed by scene id. */
  reasons: Readonly<Record<string, string>>;
  /** How far this guest strays from their anchor spot, in world units. */
  roam: number;
  /** Seconds between spoken lines. */
  talkInterval: number;
};

export const guestPersonas: readonly GuestPersona[] = [
  {
    id: "guest-lion",
    name: "Lion",
    lookId: "pose-linen",
    bio: "英语专业在读，也是花房夜宴的主理人，负责把每个人推上 T 台。",
    smallTalk: [
      "想上台就跟我说一声",
      "灯我已经调好了",
      "白衬衫最安全，也最难穿好",
      "今天人齐得刚刚好",
      "先坐，别客气"
    ],
    runwayCheers: ["请看今晚的主角", "灯光跟上", "这一套我记下了"],
    reasons: {
      "greenhouse-ball": "这场是他攒的，灯和主题都他定的。",
      "rooftop-garden": "花房散场后他把人拉上了天台。",
      "coffee-house": "他常驻这家店写作业，顺便蹭无限续杯。"
    },
    conversation: [
      { speaker: "guest", text: "嗨，你是今晚第一个走过来的。" },
      { speaker: "player", text: "这场是你办的？" },
      { speaker: "guest", text: "算是吧，我负责挑主题和布灯。" },
      { speaker: "guest", text: "本职是英语专业，办派对纯属副业。" },
      { speaker: "player", text: "那今晚的主题是什么？" },
      { speaker: "guest", text: "花房、柔光、带一点复古。" },
      { speaker: "guest", text: "换好 Look 就上台，我给你留了灯。" }
    ],
    roam: 26,
    talkInterval: 9
  },
  {
    id: "guest-fantuan",
    name: "饭团大王",
    lookId: "pose-jersey",
    bio: "大二经济学系，重度巴萨球迷，坚持球衣可以穿去任何场合。",
    smallTalk: [
      "球衣配裙子才是正解",
      "昨晚那球你看了吗",
      "迷彩其实很百搭",
      "这地板适合跑两步",
      "经济学第一课：球衣要买正版"
    ],
    runwayCheers: ["这撞色我记下了", "有精神！", "好会穿"],
    reasons: {
      "greenhouse-ball": "听说有免费的酒就来了，顺便穿球衣挑衅 dress code。",
      "rooftop-garden": "天台信号好，她在这儿看下半场。",
      "coffee-house": "咖啡馆有投屏，她提前两小时来占了位子。"
    },
    conversation: [
      { speaker: "guest", text: "你也觉得球衣能穿去舞会吧？" },
      { speaker: "player", text: "……是挺敢的。" },
      { speaker: "guest", text: "这可是巴萨，红蓝配色本身就是设计。" },
      { speaker: "player", text: "你学经济学的？" },
      { speaker: "guest", text: "大二了。不过我更擅长算转会费。" },
      { speaker: "guest", text: "下次带你去看球，穿这身就行。" }
    ],
    roam: 26,
    talkInterval: 6.5
  },
  {
    id: "guest-huanxi",
    name: "一寸欢喜",
    lookId: "pose-cargo",
    bio: "深圳来的大一传播学新生，温柔又上进，满脑子都是想做的项目。",
    smallTalk: [
      "工装裤口袋能装下整个夜晚",
      "上短下长，永远不会错",
      "我在记大家的搭配灵感",
      "今晚想被拍进合影里",
      "深圳的夜晚也是这个温度"
    ],
    runwayCheers: ["这版型可以", "松弛感满分", "想抄作业"],
    reasons: {
      "greenhouse-ball": "第一次参加，是来找项目搭子的。",
      "rooftop-garden": "跟着大家转场，想多认识几个人。",
      "coffee-house": "她把这里当自习室，也当见面地点。"
    },
    conversation: [
      { speaker: "guest", text: "你好呀，我是一寸欢喜！" },
      { speaker: "player", text: "名字很好听。" },
      { speaker: "guest", text: "嘿嘿，一寸一寸的欢喜嘛。" },
      { speaker: "guest", text: "我大一，传播学，刚从深圳过来。" },
      { speaker: "player", text: "来这边玩？" },
      { speaker: "guest", text: "顺便找搭子——我在做一个小项目。" },
      { speaker: "guest", text: "等下也想上台，你先走我就跟。" }
    ],
    roam: 26,
    talkInterval: 8.5
  },
  {
    id: "guest-shuyi",
    name: "姝宜",
    lookId: "pose-ash",
    bio: "把逛街当调研的时装脑，看一眼就知道你这件在哪买的、打几折。",
    smallTalk: [
      "同色系是最高级的偷懒",
      "这条裙子我等它降价等了三个月",
      "包不用贵，但一定要撑得住形",
      "我可以为一双鞋改整套搭配",
      "这个灯光显色太好了"
    ],
    runwayCheers: ["这版型立住了", "长度刚刚好", "买它！"],
    conversation: [
      { speaker: "guest", text: "等一下——你这件在哪买的？" },
      { speaker: "player", text: "……忘了，很久以前的。" },
      { speaker: "guest", text: "可惜，我本来想连夜下单。" },
      { speaker: "guest", text: "不过你腰线收得对，这才是重点。" },
      { speaker: "player", text: "你好像很懂这些。" },
      { speaker: "guest", text: "我把逛街当正经事做的。" },
      { speaker: "guest", text: "去台上转一圈，我帮你看比例。" }
    ],
    reasons: {
      "greenhouse-ball": "冲着「主题走秀」四个字来的，她等这种场合很久了。",
      "rooftop-garden": "天台光线好，她说这是最适合拍照的时段。",
      "coffee-house": "下午常来这家，位子靠窗，看街上的人穿什么。"
    },
    roam: 26,
    talkInterval: 7.5
  },
  {
    id: "guest-taozi",
    name: "小桃",
    lookId: "pose-crew-wide",
    bio: "现场志愿者，胸前挂着工牌，负责把每个路过的人拉来试一次产品。",
    smallTalk: [
      "要不要试一下？三十秒就好",
      "工牌别摘，等下还要检票",
      "今天已经带了四十多个人",
      "阔腿裤站一天也不累",
      "这个真的可以自己换装"
    ],
    runwayCheers: ["好看！", "这套我记下了", "再来一次！"],
    conversation: [
      { speaker: "guest", text: "你好，要不要试一下我们的产品？" },
      { speaker: "player", text: "我已经在里面了。" },
      { speaker: "guest", text: "……对哦，那你已经通关了。" },
      { speaker: "guest", text: "我是今天的志愿者，负责拉人来体验。" },
      { speaker: "player", text: "带了多少个了？" },
      { speaker: "guest", text: "四十多个吧，嗓子有点哑。" },
      { speaker: "guest", text: "但看到有人上台的时候还是会激动。" }
    ],
    reasons: {
      "greenhouse-ball": "她在门口站了一天，散场前终于自己进来玩一次。",
      "rooftop-garden": "收摊后被拉上天台，说要补一张合影。",
      "coffee-house": "轮班间隙躲进来喝口水，顺便看看别人怎么搭。"
    },
    roam: 30,
    talkInterval: 7
  },
  {
    id: "guest-tongge",
    name: "桐哥",
    lookId: "pose-crew-glasses",
    bio: "今天黑客松现场的老大。从早上布场站到现在，什么都管，什么都问一句。",
    smallTalk: [
      "网络还稳吗？有问题喊我",
      "从早上七点站到现在",
      "各位加把劲，还有时间",
      "这个交互我要记一下",
      "谁的插线板？先别拔"
    ],
    runwayCheers: ["可以啊！", "完成度不错", "这个细节做到了"],
    conversation: [
      { speaker: "guest", text: "同学，这个是你们做的？" },
      { speaker: "player", text: "是的桐哥。" },
      { speaker: "guest", text: "我本来只打算看两分钟。" },
      { speaker: "guest", text: "结果自己在里面走了二十分钟。" },
      { speaker: "player", text: "那算过关了吗？" },
      { speaker: "guest", text: "我不评分，我只负责让大家做得出来。" },
      { speaker: "guest", text: "去台上再走一次，我看看运镜。" }
    ],
    reasons: {
      "greenhouse-ball": "他是今天现场的组织者，正一个个展位试过来。",
      "rooftop-garden": "布场间隙上来透口气，顺手又打开了这个页面。",
      "coffee-house": "他说咖啡馆这版最像真实使用场景，坐下来慢慢试。"
    },
    roam: 24,
    talkInterval: 9.5
  },
  {
    id: "guest-nana",
    name: "Nana",
    lookId: "pose-visitor-skirt",
    bio: "隔壁展位跑来的同学，墨镜不摘，主要目的是拍一张能发的图。",
    smallTalk: [
      "我就是来拍照的",
      "墨镜是造型的一部分",
      "这张能发朋友圈",
      "隔壁展位没这个好玩",
      "百褶裙转起来好看"
    ],
    runwayCheers: ["拍到了！", "这张能发", "姐妹好会"],
    conversation: [
      { speaker: "guest", text: "等一下，别动——我拍一张。" },
      { speaker: "player", text: "……好。" },
      { speaker: "guest", text: "可以，这张能发。" },
      { speaker: "guest", text: "我是隔壁展位的，偷偷跑过来的。" },
      { speaker: "player", text: "那边不好玩吗？" },
      { speaker: "guest", text: "那边不能合影。" },
      { speaker: "guest", text: "等下你上台，我帮你拍全场那张。" }
    ],
    reasons: {
      "greenhouse-ball": "隔壁展位跑来的，冲着能拍合影这件事来的。",
      "rooftop-garden": "天台的光最好，她说这里出片率最高。",
      "coffee-house": "她把咖啡馆当背景板，已经拍了十几张。"
    },
    roam: 36,
    talkInterval: 6
  }
];

export function personaById(id: string): GuestPersona | undefined {
  return guestPersonas.find((persona) => persona.id === id);
}

/**
 * Scripted exchanges between two guests.
 *
 * The room should feel alive whether or not the player is involved, so pairs
 * drift together on their own and talk. Each pair gets its own script — two
 * characters who would obviously say different things to each other.
 */
export type GuestChat = {
  between: readonly [string, string];
  lines: readonly { speaker: 0 | 1; text: string }[];
};

export const guestChats: readonly GuestChat[] = [
  {
    between: ["guest-lion", "guest-shuyi"],
    lines: [
      { speaker: 0, text: "姝宜，这次灯我调暖了两度。" },
      { speaker: 1, text: "看出来了，显色好很多。" },
      { speaker: 1, text: "米色系终于不发灰了。" },
      { speaker: 0, text: "专业。下次直接你来定。" }
    ]
  },
  {
    between: ["guest-fantuan", "guest-huanxi"],
    lines: [
      { speaker: 0, text: "你也太早到了吧。" },
      { speaker: 1, text: "我来占位子的，顺便写点东西。" },
      { speaker: 0, text: "写什么？" },
      { speaker: 1, text: "一个小项目，等下讲给你听。" },
      { speaker: 0, text: "行，但先陪我看完这半场。" }
    ]
  },
  {
    between: ["guest-shuyi", "guest-huanxi"],
    lines: [
      { speaker: 1, text: "姐，我这套是不是太素了？" },
      { speaker: 0, text: "不素，是缺一个重点。" },
      { speaker: 0, text: "把袖子卷两折试试。" },
      { speaker: 1, text: "……真的不一样了！" },
      { speaker: 0, text: "对吧。细节比单品贵重要。" }
    ]
  },
  {
    between: ["guest-lion", "guest-fantuan"],
    lines: [
      { speaker: 0, text: "球衣……也算主题的一种。" },
      { speaker: 1, text: "这是巴萨，本身就是配色教科书。" },
      { speaker: 0, text: "好好好，你赢了。" },
      { speaker: 1, text: "等下上台我给你走一个。" }
    ]
  },
  {
    between: ["guest-shuyi", "guest-fantuan"],
    lines: [
      { speaker: 0, text: "你这条迷彩短裤版型不错。" },
      { speaker: 1, text: "球市淘的，两百块。" },
      { speaker: 0, text: "……你带我去。" }
    ]
  },
  {
    between: ["guest-taozi", "guest-tongge"],
    lines: [
      { speaker: 0, text: "桐哥，这是第几个展位了？" },
      { speaker: 1, text: "第十一个。腿有点酸。" },
      { speaker: 0, text: "那你坐会儿，我给你拿瓶水。" },
      { speaker: 1, text: "不用，我想先把这个走完。" }
    ]
  },
  {
    between: ["guest-nana", "guest-shuyi"],
    lines: [
      { speaker: 0, text: "你这条裙子哪买的？" },
      { speaker: 1, text: "终于有人问到点子上了。" },
      { speaker: 1, text: "等降价等了三个月。" },
      { speaker: 0, text: "……链接。" },
      { speaker: 1, text: "等下私发你。" }
    ]
  },
  {
    between: ["guest-taozi", "guest-huanxi"],
    lines: [
      { speaker: 0, text: "你也是学生吧？" },
      { speaker: 1, text: "大一，传播学。" },
      { speaker: 0, text: "那你肯定懂怎么让人愿意转发。" },
      { speaker: 1, text: "我正在学……不过合影这个我会发。" }
    ]
  },
  {
    between: ["guest-tongge", "guest-fantuan"],
    lines: [
      { speaker: 0, text: "你这身……是队服吗？" },
      { speaker: 1, text: "是巴萨主场球衣。" },
      { speaker: 0, text: "行，那也算主题的一种。" },
      { speaker: 1, text: "桐哥懂球！" }
    ]
  },
  {
    between: ["guest-nana", "guest-lion"],
    lines: [
      { speaker: 0, text: "这个灯是你调的？" },
      { speaker: 1, text: "是，暖了两度。" },
      { speaker: 0, text: "难怪出片。" }
    ]
  },
  {
    between: ["guest-lion", "guest-huanxi"],
    lines: [
      { speaker: 0, text: "第一次来还习惯吗？" },
      { speaker: 1, text: "习惯！大家都好好聊。" },
      { speaker: 0, text: "想上台随时说，我给你开灯。" },
      { speaker: 1, text: "那我再攒攒勇气。" }
    ]
  }
];

const DOUYIN_SEARCH_BASE_URL = "https://www.douyin.com/search/";

export function buildDouyinSearchUrl(query: string) {
  const keyword = query.trim() || "同款穿搭单品";
  return `${DOUYIN_SEARCH_BASE_URL}${encodeURIComponent(keyword)}`;
}

import { useEffect, useState } from "react";

import { wardrobeApi } from "../../api/client";

export function useDisplayImage(
  itemId: string,
  refreshKey: string,
  disabled = false
): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (disabled) {
      setUrl(null);
      return;
    }
    let active = true;
    let objectUrl: string | null = null;
    wardrobeApi
      .displayImage(itemId)
      .then((nextUrl) => {
        const browserUrl = nextUrl.startsWith("blob:")
          ? nextUrl
          : `${nextUrl}?v=${encodeURIComponent(refreshKey)}`;
        objectUrl = browserUrl;
        if (active) setUrl(browserUrl);
      })
      .catch(() => {
        if (active) setUrl(null);
      });
    return () => {
      active = false;
      if (objectUrl?.startsWith("blob:")) URL.revokeObjectURL(objectUrl);
    };
  }, [disabled, itemId, refreshKey]);

  return url;
}

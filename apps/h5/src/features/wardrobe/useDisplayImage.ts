import { useEffect, useState } from "react";

import { wardrobeApi } from "../../api/client";

export function useDisplayImage(itemId: string, disabled = false): string | null {
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
        objectUrl = nextUrl;
        if (active) setUrl(nextUrl);
      })
      .catch(() => {
        if (active) setUrl(null);
      });
    return () => {
      active = false;
      if (objectUrl?.startsWith("blob:")) URL.revokeObjectURL(objectUrl);
    };
  }, [disabled, itemId]);

  return url;
}

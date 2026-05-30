import { useEffect, useState } from "react";

const imageCache = new Map<string, HTMLImageElement>();

export function useHtmlImage(src: string | undefined): HTMLImageElement | undefined {
  const [image, setImage] = useState<HTMLImageElement | undefined>(() =>
    src ? imageCache.get(src) : undefined,
  );

  useEffect(() => {
    if (!src) {
      setImage(undefined);
      return;
    }

    const cached = imageCache.get(src);
    if (cached?.complete) {
      setImage(cached);
      return;
    }

    const img = cached ?? new window.Image();
    if (!cached) {
      imageCache.set(src, img);
    }

    const onLoad = () => setImage(img);
    img.addEventListener("load", onLoad);
    img.src = src;

    if (img.complete) {
      onLoad();
    }

    return () => img.removeEventListener("load", onLoad);
  }, [src]);

  return image;
}

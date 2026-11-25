import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Width of an element in CSS pixels, so SVG charts draw at true size instead of scaling text.
 * Returns a callback ref, so an element that mounts after the first render is measured too.
 */
export function useWidth<T extends HTMLElement>(initial = 600, min = 280) {
  const [width, setWidth] = useState(initial);
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((node: T | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!node) return;
    observer.current = new ResizeObserver(([entry]) => setWidth(Math.max(min, Math.floor(entry.contentRect.width))));
    observer.current.observe(node);
  }, [min]);
  useEffect(() => () => observer.current?.disconnect(), []);
  return [ref, width] as const;
}

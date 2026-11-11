import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, errorMessage, isNetworkError } from "../services/api";

export interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  networkError: boolean;
  refetch: () => void;
}

/**
 * Generic loader hook: GET `path` on mount (and whenever `path` changes),
 * exposing data / loading / error / refetch.
 */
export function useApi<T>(path: string | null): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [error, setError] = useState<string | null>(null);
  const [networkError, setNetworkError] = useState(false);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (path === null) {
      setLoading(false);
      return;
    }
    const current = ++seq.current;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNetworkError(false);
    apiGet<T>(path)
      .then((result) => {
        if (cancelled || current !== seq.current) return;
        setData(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled || current !== seq.current) return;
        setError(errorMessage(err));
        setNetworkError(isNetworkError(err));
      })
      .finally(() => {
        if (cancelled || current !== seq.current) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  return { data, loading, error, networkError, refetch };
}

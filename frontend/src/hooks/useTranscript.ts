import { useEffect, useState } from "react";
import { fetchTranscript } from "../api/mockApi";
import type { Transcript } from "../types";

export function useTranscript() {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTranscript()
      .then((data) => {
        if (!cancelled) setTranscript(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { transcript, loading, error };
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteReport, getReports } from "@/lib/api/client";
import type { ReportListItem } from "@/lib/api/schema";

export function useReportHistory(limit = 50) {
  const [rows, setRows] = useState<ReportListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await getReports(undefined, limit));
      setError(null);
    } catch (requestError) {
      console.error(requestError);
      setError("검사 이력을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    let active = true;
    getReports(undefined, limit)
      .then((reports) => {
        if (!active) return;
        setRows(reports);
        setError(null);
      })
      .catch((requestError) => {
        console.error(requestError);
        if (active) setError("검사 이력을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [limit]);

  const remove = useCallback(async (resultId: string) => {
    await deleteReport(resultId);
    setRows((current) => current.filter((row) => row.result_id !== resultId));
  }, []);

  return { rows, loading, error, refresh, remove };
}

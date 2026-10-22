"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use, useEffect } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";

type Detail = { value: { id: string; page: number }; document: { id: string } };

export default function ExtractedValuePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const q = useQuery({
    queryKey: ["extracted-value", id],
    queryFn: () => api<Detail>(`/api/extracted-values/${id}`),
  });
  useEffect(() => {
    if (!q.data) return;
    router.replace(`/evidence/${q.data.document.id}?ev=${q.data.value.id}&page=${q.data.value.page}`);
  }, [q.data, router]);
  if (q.error) return <ErrorState error={q.error} />;
  return <LoadingState label="Opening the source field…" />;
}

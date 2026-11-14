"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { api, unwrap } from "./api";
import { markMarketplaceUnavailable } from "./degraded";
import type {
  AnalyticsOut,
  ApprovalIn,
  ApprovalResult,
  ConversationOut,
  ConversationSummary,
  HealthOut,
  InboxOut,
  JobDetail,
  JobStatus,
  MemoryItem,
  PortfolioItem,
  ProfileIn,
  ProfileOut,
  Recommendation,
  RunOut,
  RunStarted,
  SavedSearch,
  Stage,
  PipelineCard,
  StudioOut,
  UploadResult,
  UserOut,
} from "./types";

export const keys = {
  me: ["me"] as const,
  profile: ["profile"] as const,
  searches: ["searches"] as const,
  portfolio: ["portfolio"] as const,
  inbox: (f: InboxFilters) => ["jobs", f] as const,
  jobs: ["jobs"] as const,
  job: (id: string) => ["job", id] as const,
  studio: (threadId: string) => ["studio", threadId] as const,
  pipeline: ["pipeline"] as const,
  conversations: ["messages"] as const,
  conversation: (id: string) => ["messages", id] as const,
  runs: ["runs"] as const,
  run: (id: string) => ["run", id] as const,
  analytics: ["analytics"] as const,
  memory: ["memory"] as const,
  health: ["health"] as const,
};

/* ---------------- auth ---------------- */

export function useMe(enabled = true) {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => unwrap<UserOut>(api.GET("/api/auth/me")),
    enabled,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      unwrap<UserOut>(api.POST("/api/auth/login", { body })),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string; name: string }) =>
      unwrap<UserOut>(api.POST("/api/auth/register", { body })),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/logout")),
    onSettled: () => qc.clear(),
  });
}

/* ---------------- profile, searches, portfolio ---------------- */

export function useProfile() {
  return useQuery({
    queryKey: keys.profile,
    queryFn: () => unwrap<ProfileOut>(api.GET("/api/profile")),
  });
}

export function useSaveProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileIn) => unwrap<ProfileOut>(api.PUT("/api/profile", { body })),
    onSuccess: (p) => {
      qc.setQueryData(keys.profile, p);
      qc.invalidateQueries({ queryKey: keys.me });
    },
  });
}

export function useSearches() {
  return useQuery({
    queryKey: keys.searches,
    queryFn: () => unwrap<SavedSearch[]>(api.GET("/api/searches")),
  });
}

export function useAddSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SavedSearch) => unwrap<SavedSearch>(api.POST("/api/searches", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.searches }),
  });
}

export function useDeleteSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (searchId: string) =>
      unwrap(api.DELETE("/api/searches/{search_id}", { params: { path: { search_id: searchId } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.searches }),
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: keys.portfolio,
    queryFn: () => unwrap<PortfolioItem[]>(api.GET("/api/portfolio/items")),
  });
}

export function useUploadPortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) =>
      unwrap<UploadResult>(
        api.POST("/api/portfolio/upload", {
          // The generated type says string[] (binary); the serializer sends real Files.
          body: { files: files as unknown as string[] },
          bodySerializer: () => {
            const fd = new FormData();
            for (const f of files) fd.append("files", f, f.name);
            return fd;
          },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.portfolio }),
  });
}

export function useDisconnectUpwork() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/oauth/upwork/disconnect")),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profile }),
  });
}

/* ---------------- jobs ---------------- */

export interface InboxFilters {
  status?: JobStatus;
  recommendation?: Recommendation;
  q?: string;
  sort?: "fit" | "newest" | "price";
}

export function useInbox(filters: InboxFilters) {
  return useQuery({
    queryKey: keys.inbox(filters),
    queryFn: async () => {
      const out = await unwrap<InboxOut>(
        api.GET("/api/jobs", {
          params: {
            query: {
              status: filters.status ?? null,
              recommendation: filters.recommendation ?? null,
              q: filters.q || null,
              sort: filters.sort ?? "fit",
              limit: 50,
            },
          },
        }),
      );
      if (out.marketplace_status && out.marketplace_status !== "ok") markMarketplaceUnavailable();
      return out;
    },
    refetchInterval: 60_000,
    placeholderData: (prev) => prev,
  });
}

export function useJob(jobId: string) {
  return useQuery({
    queryKey: keys.job(jobId),
    queryFn: () =>
      unwrap<JobDetail>(api.GET("/api/jobs/{job_id}", { params: { path: { job_id: jobId } } })),
  });
}

export function useScout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap<RunStarted>(api.POST("/api/jobs/scout")),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.jobs }),
  });
}

export function useAnalyze() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      unwrap<RunStarted>(
        api.POST("/api/jobs/{job_id}/analyze", { params: { path: { job_id: jobId } } }),
      ),
    onSuccess: (_r, jobId) => {
      qc.invalidateQueries({ queryKey: keys.job(jobId) });
      qc.invalidateQueries({ queryKey: keys.jobs });
    },
  });
}

export function useSkip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, reason }: { jobId: string; reason: string }) =>
      unwrap(
        api.POST("/api/jobs/{job_id}/skip", {
          params: { path: { job_id: jobId } },
          body: { reason },
        }),
      ),
    onSuccess: (_r, { jobId }) => {
      qc.invalidateQueries({ queryKey: keys.jobs });
      qc.invalidateQueries({ queryKey: keys.job(jobId) });
    },
  });
}

/* ---------------- studio & approvals ---------------- */

/**
 * The studio is always read from the server, including `pending_approval`,
 * so a refresh never loses a pending approval.
 */
export function useStudio(threadId: string) {
  return useQuery({
    queryKey: keys.studio(threadId),
    queryFn: () =>
      unwrap<StudioOut>(
        api.GET("/api/proposals/{thread_id}", { params: { path: { thread_id: threadId } } }),
      ),
    // While the graph is still drafting or re-checking, keep polling.
    refetchInterval: (q) =>
      q.state.data && ["drafting", "analysing"].includes(q.state.data.status) ? 5_000 : false,
  });
}

export function useRegenerate(threadId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { paragraph_index: number; instruction?: string | null }) =>
      unwrap<RunStarted>(
        api.POST("/api/proposals/{thread_id}/regenerate", {
          params: { path: { thread_id: threadId } },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.studio(threadId) }),
  });
}

export function useApproval(threadId: string, alsoInvalidate: QueryKey[] = []) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApprovalIn) =>
      unwrap<ApprovalResult>(
        api.POST("/api/approvals/{thread_id}", {
          params: { path: { thread_id: threadId } },
          body,
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.studio(threadId) });
      qc.invalidateQueries({ queryKey: keys.pipeline });
      qc.invalidateQueries({ queryKey: keys.jobs });
      for (const k of alsoInvalidate) qc.invalidateQueries({ queryKey: k });
    },
  });
}

/* ---------------- pipeline ---------------- */

export function usePipeline() {
  return useQuery({
    queryKey: keys.pipeline,
    queryFn: async () => {
      const out = await unwrap<{ columns: Partial<Record<Stage, PipelineCard[]>> }>(
        api.GET("/api/pipeline"),
      );
      return out;
    },
    refetchInterval: 15_000,
  });
}

/* ---------------- messages ---------------- */

export function useConversations() {
  return useQuery({
    queryKey: keys.conversations,
    queryFn: () => unwrap<ConversationSummary[]>(api.GET("/api/messages")),
    refetchInterval: 30_000,
  });
}

export function useConversation(id: string) {
  return useQuery({
    queryKey: keys.conversation(id),
    queryFn: () =>
      unwrap<ConversationOut>(
        api.GET("/api/messages/{conversation_id}", {
          params: { path: { conversation_id: id } },
        }),
      ),
    refetchInterval: 30_000,
  });
}

export function useDraftReply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) =>
      unwrap<RunStarted>(
        api.POST("/api/messages/{conversation_id}/draft", {
          params: { path: { conversation_id: conversationId } },
        }),
      ),
    onSuccess: (_r, id) => qc.invalidateQueries({ queryKey: keys.conversation(id) }),
  });
}

/* ---------------- runs ---------------- */

export function useRuns() {
  return useQuery({
    queryKey: keys.runs,
    queryFn: () => unwrap<RunOut[]>(api.GET("/api/runs", { params: { query: { limit: 30 } } })),
    refetchInterval: 15_000,
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: keys.run(runId),
    queryFn: () =>
      unwrap<RunOut>(api.GET("/api/runs/{run_id}", { params: { path: { run_id: runId } } })),
  });
}

/* ---------------- analytics, memory, health ---------------- */

export function useAnalytics() {
  return useQuery({
    queryKey: keys.analytics,
    queryFn: () => unwrap<AnalyticsOut>(api.GET("/api/analytics")),
  });
}

export function useMemory() {
  return useQuery({
    queryKey: keys.memory,
    queryFn: async () => (await unwrap<{ items: MemoryItem[] }>(api.GET("/api/memory"))).items,
  });
}

export function useDeleteMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ namespace, key }: { namespace: string; key: string }) =>
      unwrap(
        api.DELETE("/api/memory/{namespace}/{key}", {
          params: { path: { namespace, key } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.memory }),
  });
}

export function useHealth() {
  return useQuery({
    queryKey: keys.health,
    queryFn: () => unwrap<HealthOut>(api.GET("/api/health")),
    refetchInterval: 20_000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}

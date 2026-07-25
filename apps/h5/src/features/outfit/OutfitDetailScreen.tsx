import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { wardrobeApi } from "../../api/client";
import { LookDetail } from "../wardrobe/LookDetail";

interface OutfitDetailScreenProps {
  outfitId: string;
  onBack: () => void;
  onReturnToSource?: (videoRef: string, timestampMs: number) => void;
}

export function OutfitDetailScreen({
  outfitId,
  onBack,
  onReturnToSource
}: OutfitDetailScreenProps) {
  const queryClient = useQueryClient();
  const lookQuery = useQuery({
    queryKey: ["wardrobe-look", outfitId],
    queryFn: () => wardrobeApi.getLook(outfitId),
    refetchInterval: (query) =>
      query.state.data?.look.status === "processing" ||
      query.state.data?.look.status === "partial"
        ? 2_000
        : false
  });

  const retryMutation = useMutation({
    mutationFn: (lookId: string) => wardrobeApi.retryLook(lookId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-looks"] });
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-look", outfitId] });
    }
  });

  const reasonMutation = useMutation({
    mutationFn: ({ lookId, reason }: { lookId: string; reason: string }) =>
      wardrobeApi.addLikingReason(lookId, reason, crypto.randomUUID()),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-look", outfitId] });
    }
  });

  return (
    <LookDetail
      detail={lookQuery.data ?? null}
      loading={lookQuery.isLoading}
      retrying={retryMutation.isPending}
      saving={reasonMutation.isPending}
      onClose={onBack}
      onReturnToSource={(videoRef, timestampMs) => {
        if (onReturnToSource) {
          onReturnToSource(videoRef, timestampMs);
          return;
        }
        onBack();
      }}
      onRetry={(lookId) => retryMutation.mutate(lookId)}
      onSaveReason={(lookId, reason) => reasonMutation.mutate({ lookId, reason })}
    />
  );
}

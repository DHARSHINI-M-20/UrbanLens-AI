type BedrockMetric = Record<string, unknown>;

export interface BedrockExecutionStatus {
  verified: boolean;
  message: string;
}

function positiveCount(value: unknown): number {
  const count = Number(value);
  return Number.isFinite(count) && count > 0 ? count : 0;
}

/** Derive execution status only from an explicit successful invocation record. */
export function getBedrockExecutionStatus(metrics: BedrockMetric[], observations: BedrockMetric[] = []): BedrockExecutionStatus {
  const successful = metrics.find((metric) =>
    metric.bedrock_status === "success" &&
    positiveCount(metric.bedrock_invocations) > 0 &&
    positiveCount(metric.bedrock_invocation_attempts) > 0,
  );

  if (successful) {
    const timestamp = typeof successful.timestamp === "string" && !Number.isNaN(Date.parse(successful.timestamp))
      ? successful.timestamp
      : null;
    if (timestamp) {
      return {
        verified: true,
        message: `Bedrock execution: VERIFIED · ${positiveCount(successful.bedrock_invocations)} successful invocation(s) · ${timestamp}`,
      };
    }
  }

  const successfulReview = observations.find((observation) => {
    const review = observation.bedrock_review as BedrockMetric | undefined;
    return review?.status === "attempted_success" && review.attempted === true &&
      review.aws_service === "Amazon Bedrock Runtime" &&
      review.processing_route === "bedrock_nova_lite_escalation" &&
      review.result != null;
  });
  if (successfulReview) {
    return {
      verified: true,
      message: "Bedrock execution: VERIFIED · a successful Bedrock result is persisted on an observation; execution timestamp is unavailable.",
    };
  }

  if (successful) {
    return {
      verified: false,
      message: "Bedrock execution: NOT VERIFIED · a successful invocation is recorded, but its timestamp is missing.",
    };
  }

  const alreadyReviewed = metrics.find((metric) => metric.bedrock_status === "already_reviewed");
  if (alreadyReviewed) {
    return {
      verified: false,
      message: "Bedrock execution: NOT VERIFIED · the persisted run is already_reviewed (0 new invocations); its retained latency does not prove execution, and no successful invocation timestamp is exposed.",
    };
  }

  return {
    verified: false,
    message: "Bedrock execution: NOT VERIFIED · no persisted successful invocation record and timestamp are available.",
  };
}

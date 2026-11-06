interface TraceBadgeProps {
  traceId: string;
  confidence?: number;
}

export function TraceBadge({ traceId, confidence }: TraceBadgeProps) {
  return (
    <div className="trace-line">
      TraceId: {traceId}
      {confidence !== undefined && (
        <> · Độ tin cậy: {(confidence * 100).toFixed(1)}%</>
      )}
    </div>
  );
}
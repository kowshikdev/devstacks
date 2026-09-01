import { Skeleton } from "../components/ui/Feedback";

export default function Loading() {
  return (
    <div className="container" style={{ padding: "var(--space-10) var(--space-4)" }}>
      <div className="stack gap-4" style={{ maxWidth: 640 }}>
        <Skeleton width="35%" height={14} />
        <Skeleton width="70%" height={32} />
        <Skeleton width="90%" height={14} />
        <Skeleton width="80%" height={14} />
      </div>
    </div>
  );
}

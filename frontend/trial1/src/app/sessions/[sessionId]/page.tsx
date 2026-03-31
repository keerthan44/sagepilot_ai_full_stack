import Link from 'next/link';
import { SessionDetail } from '@/features/voice/components/SessionDetail';

interface SessionDetailPageProps {
  params: Promise<{ sessionId: string }>;
}

export default async function SessionDetailPage({ params }: SessionDetailPageProps) {
  const { sessionId } = await params;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center gap-3">
        <Link
          href="/sessions"
          className="text-muted-foreground hover:text-foreground text-sm transition-colors"
        >
          ← Sessions
        </Link>
      </div>
      <SessionDetail sessionId={sessionId} />
    </div>
  );
}

import { SessionList } from '@/features/voice/components/SessionList';

export default function SessionsPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Sessions</h1>
        <p className="text-muted-foreground mt-1 text-sm">Browse all past voice call sessions.</p>
      </div>
      <SessionList />
    </div>
  );
}

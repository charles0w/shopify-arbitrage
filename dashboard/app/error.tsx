"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="p-8">
      <div className="max-w-lg mx-auto mt-8 bg-zinc-900 border border-rose-500/30 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-rose-400 mb-2">
          Something went wrong
        </h2>
        <p className="text-sm text-zinc-400 mb-4">
          {error.message || "An unexpected error occurred while loading this page."}
        </p>
        {error.digest && (
          <p className="text-xs font-mono text-zinc-600 mb-4">
            digest: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
        >
          Try again
        </button>
      </div>
    </div>
  );
}

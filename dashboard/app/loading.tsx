export default function Loading() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <div className="h-7 w-48 bg-zinc-800 rounded animate-pulse" />
        <div className="h-4 w-72 bg-zinc-900 rounded mt-2 animate-pulse" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-4"
          >
            <div className="h-3 w-24 bg-zinc-800 rounded animate-pulse" />
            <div className="h-8 w-16 bg-zinc-800 rounded mt-3 animate-pulse" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="bg-zinc-900 border border-zinc-800 rounded-xl h-72 animate-pulse"
          />
        ))}
      </div>
    </div>
  );
}

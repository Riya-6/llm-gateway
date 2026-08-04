function App() {
  return (
    <main className="min-h-screen bg-slate-950 p-10 text-slate-100">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-slate-900/70 p-10 shadow-2xl">
        <p className="mb-3 text-sm uppercase tracking-[0.3em] text-cyan-400">LLM Gateway</p>
        <h1 className="text-4xl font-semibold">Multi-LLM Gateway and Evaluation Platform</h1>
        <p className="mt-4 max-w-3xl text-lg text-slate-300">
          A production-grade scaffold for routing, evaluating, caching, and observing LLM requests across providers.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-800/70 p-5">
            <h2 className="font-medium">Backend</h2>
            <p className="mt-2 text-sm text-slate-400">FastAPI services, clean architecture, and API design.</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-800/70 p-5">
            <h2 className="font-medium">Observability</h2>
            <p className="mt-2 text-sm text-slate-400">Request tracing, metrics, caching, and health checks.</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-800/70 p-5">
            <h2 className="font-medium">Evaluation</h2>
            <p className="mt-2 text-sm text-slate-400">Compare models, assess quality, and track cost and latency.</p>
          </div>
        </div>
      </div>
    </main>
  );
}

export default App;

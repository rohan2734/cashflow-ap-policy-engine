export default function Home() {
  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>CashFlo</h1>
      <p>Policy-to-Rule Engine — UI implemented in Phase 8.</p>
      <ul>
        <li>
          <a href="http://localhost:8000/docs">API docs (Swagger)</a>
        </li>
        <li>
          <a href="http://localhost:3001">Langfuse observability</a>
        </li>
      </ul>
    </main>
  );
}

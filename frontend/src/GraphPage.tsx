import React, { useEffect, useState } from "react";

const GraphPage = () => {
  const [graphUrl, setGraphUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        setLoading(true);
        setError(null);

        // Ez a fetch hívja a backendedet, hogy lefusson a Python script és visszadja a gráf URL-t
        const response = await fetch("http://localhost:3001/api/graph");

        if (!response.ok) {
          throw new Error(`Hiba a backend API hívásakor: ${response.statusText}`);
        }

        const data = await response.json();
        setGraphUrl(data.url);
      } catch (err: any) {
        setError(err.message || "Ismeretlen hiba");
      } finally {
        setLoading(false);
      }
    };

    fetchGraph();
  }, []);

  if (loading) return <div style={{ padding: "1rem", color: "white" }}>Betöltés...</div>;
  if (error) return <div style={{ padding: "1rem", color: "red" }}>Hiba: {error}</div>;

  return (
    <div style={{ width: "100vw", height: "100vh", overflow: "hidden" }}>
      {graphUrl ? (
        <iframe
          src={graphUrl}
          title="Asszociációs Gráf"
          style={{ width: "100vw", height: "100vh", border: "none" }}
        />
      ) : (
        <div style={{ color: "white" }}>Nem érhető el a gráf.</div>
      )}
    </div>
  );
};

export default GraphPage;

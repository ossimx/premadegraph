import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from "react-router-dom";
import MatchAnalysisForm from "./MatchAnalysisForm";
import GraphPage from "./GraphPage";
import { FaSyncAlt } from "react-icons/fa";

function Navbar() {
  const [loading, setLoading] = useState(false);

  const normalizePlayers = async () => {
    setLoading(true);
    try {
      const response = await fetch("http://localhost:3001/api/normalize-players", {
        method: "POST"
      });

      const result = await response.json();

      if (!response.ok) {
        console.error("Normalization failed:", result);
        alert("Hiba: " + result.error);
      } else {
        console.log("Normalization successful:", result.message);
        alert("Normalizálás sikeres!");
      }
    } catch (error) {
      console.error("Request error:", error);
      alert("Hiba történt a normalizálás során.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <nav style={{
      backgroundColor: "#222",
      padding: "1rem 2rem",
      display: "flex",
      gap: "1.5rem",
      alignItems: "center"
    }}>
      <Link to="/matchanalysis" style={{ color: "white", textDecoration: "none", fontWeight: "bold" }}>
        Meccselemzés
      </Link>
      <Link to="/graph" style={{ color: "white", textDecoration: "none", fontWeight: "bold" }}>
        Asszociációs Gráf
      </Link>
      <button onClick={async () => {
        setLoading(true);
        try {
          const res = await fetch("http://localhost:3001/api/generate-graph", {
            method: "POST",
          });
          if (!res.ok) throw new Error("Nem sikerült generálni a gráfot.");
          alert("Gráf generálva! Frissítsd az oldalt a megtekintéshez.");
        } catch (e: any) {
          alert("Hiba történt: " + (e.message || "Ismeretlen"));
        } finally {
          setLoading(false);
        }
      }}>
        Gráf generálása
      </button>

      <button
        onClick={normalizePlayers}
        title="Normalizálás"
        disabled={loading}
        style={{
          background: "none",
          border: "none",
          color: "white",
          cursor: loading ? "not-allowed" : "pointer",
          marginLeft: "auto",
          fontSize: "1.2rem",
          display: "flex",
          alignItems: "center"
        }}
      >
        {loading ? (
          <span className="spinner" style={{
            width: "1rem",
            height: "1rem",
            border: "2px solid white",
            borderTop: "2px solid transparent",
            borderRadius: "50%",
            animation: "spin 1s linear infinite"
          }} />
        ) : (
          <FaSyncAlt />
        )}
      </button>
    </nav>
  );
}

// Add CSS for spinner animation
const style = document.createElement('style');
style.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(style);

function App() {
  return (
    <Router>
      <div style={{ background: "rgba(118, 118, 118, 0.8)" }}>
        <Navbar />
        <Routes>
          <Route path="/matchanalysis" element={<MatchAnalysisForm />} />
          <Route path="/graph" element={<GraphPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
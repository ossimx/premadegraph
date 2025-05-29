const express = require("express");
const fs = require("fs");
const path = require("path");
const cors = require("cors");
const bodyParser = require("body-parser");
const sqlite3 = require('sqlite3').verbose();
const app = express();
const PORT = 3001;
const MATCHES_DIR = path.join(__dirname, "data");
const { exec } = require("child_process");
const { normalizePlayersByPuuid } = require("./normalize_players_by_puuid");

app.use(cors());
app.use(bodyParser.json());
app.use('/graph-view', express.static(path.join(__dirname, 'output')));
const backendDir = "C:\\Users\\karol\\OneDrive\\Dokumentumok\\Dolgozat\\src\\backend";
const dbPath = path.resolve(__dirname, 'players.db');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Nem sikerült megnyitni az adatbázist:', err.message);
  } else {
    console.log('Adatbázis megnyitva.');
  }
});
// Ellenőrizd, hogy a data mappa létezik-e
if (!fs.existsSync(MATCHES_DIR)) {
  fs.mkdirSync(MATCHES_DIR);
}

// POST /api/save-match
app.post("/api/save-match", (req, res) => {
  const match = req.body;
  const matchId = match?.metadata?.matchId;
  if (!matchId) {
    return res.status(400).json({ error: "Missing matchId" });
  }

  const matchFilePath = path.join(MATCHES_DIR, `${matchId}.json`);

  if (fs.existsSync(matchFilePath)) {
    return res.status(200).json({ message: "Match already exists" });
  }

  fs.writeFileSync(matchFilePath, JSON.stringify(match, null, 2));
  return res.status(201).json({ message: "Match saved" });
});

// GET /api/matches → összes meccs kilistázása
app.get("/api/matches", (req, res) => {
  const files = fs.readdirSync(MATCHES_DIR).filter(f => f.endsWith(".json"));
  const allMatches = files.map(f => {
    const content = fs.readFileSync(path.join(MATCHES_DIR, f), "utf-8");
    return JSON.parse(content);
  });
  res.json(allMatches);
});
// Database setup
db.run(`
CREATE TABLE IF NOT EXISTS players (
  puuid TEXT PRIMARY KEY,
  names TEXT,
  feedscore REAL,
  opscore REAL,
  country TEXT,
  match_count INTEGER DEFAULT 1
)
`);

app.post('/api/save-player', (req, res) => {
  const player = req.body;

  if (!player.name) {
    return res.status(400).json({ error: 'Missing player name' });
  }

  db.get("SELECT * FROM players WHERE names = ?", [player.name], (err, row) => {
    if (err) {
      console.error('Database error:', err);
      return res.status(500).json({ error: 'Database error', details: err.message });
    }

    if (row) {
      // Update existing player with weighted average calculation
      const oldCount = row.match_count || 1;
      const newCount = oldCount + 1;

      const newFeedscore = (row.feedscore * oldCount + parseFloat(player.feedscore)) / newCount;
      const newOpscore = (row.opscore * oldCount + parseFloat(player.opscore)) / newCount;

      const sqlUpdate = `
        UPDATE players SET
          feedscore = ?,
          opscore = ?,
          country = ?,
          match_count = ?
        WHERE names = ?
      `;

      db.run(sqlUpdate, [newFeedscore, newOpscore, player.country, newCount, player.name], function (err) {
        if (err) {
          console.error('Update error:', err);
          return res.status(500).json({ error: 'Update failed', details: err.message });
        }
        res.json({
          message: 'Player updated successfully',
          player: {
            name: player.name,
            feedscore: newFeedscore,
            opscore: newOpscore,
            country: player.country,
            match_count: newCount
          }
        });
      });
    } else {
      // Insert new player
      const sqlInsert = `
        INSERT OR REPLACE INTO players (names, feedscore, opscore, country, match_count)
        VALUES (?, ?, ?, ?, 1)
      `;

      db.run(sqlInsert, [player.name, parseFloat(player.feedscore), parseFloat(player.opscore), player.country], function (err) {
        if (err) {
          console.error('Insert error:', err);
          return res.status(500).json({ error: 'Insert failed', details: err.message });
        }
        res.json({
          message: 'Player inserted successfully',
          player: {
            name: player.name,
            feedscore: parseFloat(player.feedscore),
            opscore: parseFloat(player.opscore),
            country: player.country,
            match_count: 1
          }
        });
      });
    }
  });
});

app.post("/api/generate-graph", (req, res) => {
  exec(`cd "${backendDir}" && python build_graph.py --connected-only --min-weight 2`, (error, stdout, stderr) => {
    if (error) {
      console.error("Python script error:", error);
      return res.status(500).json({ message: "Python script execution failed." });
    }
    if (stderr) {
      console.warn("Python script stderr:", stderr);
    }
    console.log("Graph generated successfully.");
    res.json({ message: "Graph generation completed." });
  });
});

app.get("/api/graph", (req, res) => {
  res.json({
    url: "http://localhost:3001/graph-view/premade_network.html"
  });
});

// Serve static HTML graph
app.use("/graph-view", express.static(path.join(backendDir, "output")));
app.post("/api/normalize-players", async (req, res) => {
  try {
    await normalizePlayersByPuuid();
    res.status(200).json({ message: "Players normalized successfully." });
  } catch (err) {
    console.error("Normalization error:", err);
    res.status(500).json({ error: "Normalization failed.", details: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Backend listening at http://localhost:${PORT}`);
});
app.get("/api/ping", (req, res) => {
  res.send("pong");
});
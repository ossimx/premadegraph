const fs = require("fs");
const path = require("path");
const sqlite3 = require("sqlite3").verbose();

const dbFile = "../playersrefined.db";
const matchDir = path.join(__dirname, "data");

function addNewPlayersFromMatches() {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(dbFile);

    db.serialize(() => {
      db.run(`
        CREATE TABLE IF NOT EXISTS players (
          puuid TEXT PRIMARY KEY,
          names TEXT,
          feedscore REAL,
          opscore REAL,
          country TEXT,
          match_count INTEGER
        )
      `);

      db.all(`SELECT puuid FROM players`, [], (err, rows) => {
        if (err) {
          db.close();
          return reject("Failed to fetch existing puuids: " + err);
        }

        const existingPuuids = new Set(rows.map(r => r.puuid));
        const files = fs.readdirSync(matchDir).filter(f => f.endsWith(".json"));
        const stmt = db.prepare(`
          INSERT INTO players (puuid, names, feedscore, opscore, country, match_count)
          VALUES (?, ?, ?, ?, ?, ?)
        `);

        let newPlayerCount = 0;

        for (const file of files) {
          const data = JSON.parse(fs.readFileSync(path.join(matchDir, file), "utf-8"));
          for (const p of data.info.participants) {
            const puuid = p.puuid;
            if (existingPuuids.has(puuid)) continue;

            const name = `${p.riotIdGameName}#${p.riotIdTagline}`;
            const feedscore = p.deaths - (p.kills + p.assists) * 0.35;
            const opscore = p.kills + p.assists * 0.965 + p.goldEarned / 560 + p.visionScore * 0.15;

            stmt.run(
              puuid,
              JSON.stringify([name]),
              feedscore,
              opscore,
              " ", // country placeholder
              1
            );

            console.log(" Added:", name, "→", puuid);
            existingPuuids.add(puuid);
            newPlayerCount++;
          }
        }

        stmt.finalize(() => {
          db.close();
          console.log(` Done! Total new players added: ${newPlayerCount}`);
          resolve();
        });
      });
    });
  });
}

addNewPlayersFromMatches();

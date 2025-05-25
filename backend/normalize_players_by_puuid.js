const fs = require("fs");
const path = require("path");
const sqlite3 = require("sqlite3").verbose();

const dbFile = "../playersrefined.db";
const matchDir = path.join(__dirname, "data");

async function normalizePlayersByPuuid() {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(dbFile);

    const playersMap = new Map();

    try {
      const files = fs.readdirSync(matchDir).filter(f => f.endsWith(".json"));

      for (const file of files) {
        const data = JSON.parse(fs.readFileSync(path.join(matchDir, file), "utf-8"));
        for (const p of data.info.participants) {
          const puuid = p.puuid;
          const name = `${p.riotIdGameName}#${p.riotIdTagline}`;
          const feedscore = p.deaths - (p.kills + p.assists) * 0.35;
          const opscore = p.kills + p.assists * 0.965 + p.goldEarned / 560 + p.visionScore * 0.15;

          if (!playersMap.has(puuid)) {
            playersMap.set(puuid, {
              names: new Set([name]),
              feedscoreSum: feedscore,
              opscoreSum: opscore,
              match_count: 1,
              country: null,
            });
          } else {
            const player = playersMap.get(puuid);
            player.names.add(name);
            player.feedscoreSum += feedscore;
            player.opscoreSum += opscore;
            player.match_count += 1;
          }
        }
      }
    } catch (err) {
      return reject(err);
    }

    db.serialize(() => {
      db.run(`DROP TABLE IF EXISTS players`);
      db.run(`
        CREATE TABLE players (
          puuid TEXT PRIMARY KEY,
          names TEXT,
          feedscore REAL,
          opscore REAL,
          country TEXT,
          match_count INTEGER
        )
      `);

      const stmt = db.prepare(`
        INSERT INTO players (puuid, names, feedscore, opscore, country, match_count)
        VALUES (?, ?, ?, ?, ?, ?)
      `);

      for (const [puuid, data] of playersMap) {
        const avgFeed = data.feedscoreSum / data.match_count;
        const avgOp = data.opscoreSum / data.match_count;

        stmt.run(
          puuid,
          JSON.stringify([...data.names]),
          avgFeed,
          avgOp,
          data.country,
          data.match_count
        );
      }

      stmt.finalize((err) => {
        db.close();
        if (err) reject(err);
        else resolve();
      });
    });
  });
}

module.exports = { normalizePlayersByPuuid };
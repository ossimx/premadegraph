const fs = require("fs");
const path = require("path");
const sqlite3 = require("sqlite3").verbose();

const dbFile = "../playersrefined.db";
const matchDir = path.join(__dirname, "data");

// Normalize opscore to 0-10 scale using actual data thresholds
function normalizeOpScore(rawOpScore) {
  // Based on actual analyzed data:
  // Average: 456.02, Min: 146.92, Max: 1252.11
  
  const thresholds = [
    { score: 1252.11, grade: 10.0 },  // Maximum
    { score: 874.65, grade: 9.0 },   // Top 1%
    { score: 751.02, grade: 8.0 },   // Top 5%
    { score: 675.50, grade: 7.0 },   // Top 10%
    { score: 600, grade: 6.0 },      // Interpolated
    { score: 512.91, grade: 5.0 },   // Top 25%
    { score: 424.93, grade: 4.0 },   // Median (50%)
    { score: 350, grade: 3.0 },      // Interpolated
    { score: 280, grade: 2.0 },      // Interpolated
    { score: 220, grade: 1.0 },      // Interpolated
    { score: 146.92, grade: 0.0 }    // Minimum
  ];

  // Handle edge cases
  if (rawOpScore >= 1252.11) return 10.0;
  if (rawOpScore <= 146.92) return 0.0;

  // Find the two thresholds this score falls between and interpolate
  for (let i = 0; i < thresholds.length - 1; i++) {
    const upper = thresholds[i];
    const lower = thresholds[i + 1];
    
    if (rawOpScore <= upper.score && rawOpScore > lower.score) {
      // Linear interpolation between the two points
      const scoreRange = upper.score - lower.score;
      const gradeRange = upper.grade - lower.grade;
      const scoreOffset = rawOpScore - lower.score;
      const interpolatedGrade = lower.grade + (scoreOffset / scoreRange) * gradeRange;
      
      // Round to 2 decimal places
      return Math.round(interpolatedGrade * 100) / 100;
    }
  }

  // Fallback (shouldn't reach here)
  return 0.0;
}

async function normalizePlayersByPuuid() {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(dbFile);

    const playersMap = new Map();
    let totalMatches = 0;
    let totalPlayers = 0;

    // Start fresh - clear existing data and reset match counts
    db.serialize(() => {
      db.run(`UPDATE players SET opscore = 0, feedscore = 0, match_count = 0 WHERE 1=1`);
      try {
        const files = fs.readdirSync(matchDir).filter(f => f.endsWith(".json"));
        console.log(`Processing ${files.length} match files...`);

        for (const file of files) {
          try {
            const data = JSON.parse(fs.readFileSync(path.join(matchDir, file), "utf-8"));
            
            // Validate that the JSON has the expected structure
            if (!data.info || !data.info.participants) {
              console.warn(`Skipping ${file}: Invalid structure`);
              continue;
            }

            totalMatches++;
            const gameDurationSeconds = data.info.gameDuration;
            const gameDurationMinutes = gameDurationSeconds / 60;
            
            for (const p of data.info.participants) {
              // Validate required fields
              if (!p.puuid) {
                console.warn(`Skipping participant in ${file}: Missing puuid`);
                continue;
              }

              const puuid = p.puuid;
              const name = `${p.riotIdGameName || 'Unknown'}#${p.riotIdTagline || 'Unknown'}`;
              
              // Handle potential missing values with defaults
              const kills = p.kills || 0;
              const deaths = p.deaths || 0;
              const assists = p.assists || 0;
              const goldEarned = p.goldEarned || 0;
              const visionScore = p.visionScore || 0;
              const feedscore = deaths - (kills + assists) * 0.35;
              const rawOpScore = kills + assists * 0.965 + goldEarned / gameDurationMinutes + visionScore * 0.15;

              if (!playersMap.has(puuid)) {
                playersMap.set(puuid, {
                  names: new Set([name]),
                  feedscoreSum: feedscore,
                  opscoreSum: rawOpScore,
                  match_count: 1,
                  country: null,
                });
                totalPlayers++;
              } else {
                const player = playersMap.get(puuid);
                player.names.add(name);
                player.feedscoreSum += feedscore;
                player.opscoreSum += rawOpScore;
                player.match_count += 1;
              }
            }
          } catch (fileErr) {
            console.error(`Error processing file ${file}:`, fileErr.message);
            continue;
          }
        }

        console.log(`Processed ${totalMatches} matches and found ${totalPlayers} unique players`);
        
        // Log some statistics
        const matchCounts = Array.from(playersMap.values()).map(p => p.match_count);
        const avgMatches = matchCounts.reduce((a, b) => a + b, 0) / matchCounts.length;
        const maxMatches = Math.max(...matchCounts);
        const minMatches = Math.min(...matchCounts);
        
        console.log(`Match count stats - Avg: ${avgMatches.toFixed(2)}, Min: ${minMatches}, Max: ${maxMatches}`);

        // Create table with original structure if it doesn't exist
        db.run(`CREATE TABLE IF NOT EXISTS players (
          puuid TEXT PRIMARY KEY,
          names TEXT,
          feedscore REAL,
          opscore REAL,
          country TEXT,
          match_count INTEGER
        )`);

        // Insert all players with NORMALIZED opscores in the opscore column
        const stmt = db.prepare(`
          INSERT OR REPLACE INTO players (puuid, names, feedscore, opscore, country, match_count)
          VALUES (?, ?, ?, ?, ?, ?)
        `);

        let insertedCount = 0;
        const rawOpScores = [];
        const normalizedOpScores = [];
        
        // Create log file for raw scores
        const logFilePath = path.join(__dirname, "raw_scores_log.txt");
        const logStream = fs.createWriteStream(logFilePath, { flags: 'w' });
        logStream.write("puuid;avgopscore_before_normalization\n");
        
        for (const [puuid, data] of playersMap) {
          const avgFeed = data.feedscoreSum / data.match_count;
          const avgRawOp = data.opscoreSum / data.match_count;
          const normalizedOp = normalizeOpScore(avgRawOp);
          
          // Log to file
          logStream.write(`${puuid};${avgRawOp.toFixed(2)}\n`);
          
          rawOpScores.push(avgRawOp);
          normalizedOpScores.push(normalizedOp);

          stmt.run(
            puuid,
            JSON.stringify([...data.names]),
            avgFeed,
            normalizedOp, // Store normalized score in opscore column
            data.country,
            data.match_count
          );
          insertedCount++;
        }

        // Close log stream
        logStream.end();
        console.log(`Raw scores logged to: ${logFilePath}`);

        console.log(`Inserted ${insertedCount} players in database with normalized opscores`);

        // Log normalization statistics
        const avgRaw = rawOpScores.reduce((a, b) => a + b, 0) / rawOpScores.length;
        const minRaw = Math.min(...rawOpScores);
        const maxRaw = Math.max(...rawOpScores);
        
        const avgNormalized = normalizedOpScores.reduce((a, b) => a + b, 0) / normalizedOpScores.length;
        const minNormalized = Math.min(...normalizedOpScores);
        const maxNormalized = Math.max(...normalizedOpScores);
        
        console.log(`Raw opscore stats - Avg: ${avgRaw.toFixed(2)}, Min: ${minRaw.toFixed(2)}, Max: ${maxRaw.toFixed(2)}`);
        console.log(`Normalized opscore stats - Avg: ${avgNormalized.toFixed(2)}, Min: ${minNormalized.toFixed(2)}, Max: ${maxNormalized.toFixed(2)}`);
        
        // Show distribution of normalized scores
        const bins = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
        const distribution = new Array(bins.length - 1).fill(0);
        
        for (const score of normalizedOpScores) {
          for (let i = 0; i < bins.length - 1; i++) {
            if (score >= bins[i] && score < bins[i + 1]) {
              distribution[i]++;
              break;
            } else if (score === 10 && i === bins.length - 2) {
              distribution[i]++;
              break;
            }
          }
        }
        
        console.log('Normalized score distribution:');
        for (let i = 0; i < distribution.length; i++) {
          const range = i === distribution.length - 1 ? `${bins[i]}-${bins[i + 1]}` : `${bins[i]}-${bins[i + 1]}`;
          console.log(`  ${range}: ${distribution[i]} players`);
        }

        stmt.finalize((err) => {
          db.close();
          if (err) reject(err);
          else resolve();
        });

      } catch (err) {
        db.close();
        return reject(err);
      }
    });
  });
}

module.exports = { normalizePlayersByPuuid };

// Only run if this file is executed directly
if (require.main === module) {
  normalizePlayersByPuuid()
    .then(() => console.log("Player normalization completed successfully!"))
    .catch(err => console.error("Error during normalization:", err));
}
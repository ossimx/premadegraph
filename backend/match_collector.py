import sqlite3
import requests
import json
import time
import random
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
DB_PATH = "../playersrefined.db"  # Path to your player database
API_KEY = os.getenv("RIOT_API_KEY")
BACKEND_URL = "http://localhost:3001/api/save-match"
MATCHES_DIR = "./data"  # Where match files are stored locally

# Rate limiting settings
REQUESTS_PER_SECOND = 15    # Use 15 out of 20 available per second to be safe
REQUESTS_PER_2MIN = 90    # Use 80 out of 100 available per 2 minutes to be safe
DELAY_BETWEEN_REQUESTS = 1.0 / REQUESTS_PER_SECOND

# Fetch settings
MATCHES_PER_PLAYER = 15  # How many matches to fetch per player
MAX_ITERATIONS = 50 # Maximum number of players to process
QUEUE_TYPE = ""

# === SPECIFIC PUUID OPTION ===
# Set this to a specific PUUID to crawl only that player's matches
# Leave as None to use random player selection
SPECIFIC_PUUID = None
# Example: SPECIFIC_PUUID = "your-specific-puuid-here"

class MatchCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"X-Riot-Token": API_KEY})
        self.processed_players = set()
        self.total_matches_saved = 0
        self.total_api_calls = 0
        self.requests_in_current_2min = 0
        self.two_min_window_start = time.time()
        
    def get_random_player_with_low_matches(self):
        """Get a random player from database, preferring those with fewer existing matches"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            query = """
            SELECT puuid, names 
            FROM players 
            WHERE puuid NOT IN ({})
            ORDER BY RANDOM()
            LIMIT 50
            """.format(','.join(['?' for _ in self.processed_players]))
            
            if self.processed_players:
                cursor.execute(query, list(self.processed_players))
            else:
                cursor.execute("SELECT puuid, names FROM players ORDER BY RANDOM() LIMIT 50")
            
            candidates = cursor.fetchall()
            
            if not candidates:
                print("No more players to process!")
                return None, None
                
            # Pick the first candidate (already randomized)
            puuid, names = candidates[0]
            return puuid, names
            
        finally:
            conn.close()
    
    def get_specific_player_info(self, puuid):
        """Get player info for a specific PUUID from database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT puuid, names FROM players WHERE puuid = ?", (puuid,))
            result = cursor.fetchone()
            
            if result:
                return result[0], result[1]
            else:
                # If not in database, return PUUID with unknown name
                return puuid, "Unknown Player"
                
        finally:
            conn.close()
    
    def check_rate_limits(self):
        """Check and enforce both rate limits"""
        current_time = time.time()
        
        # Check 2-minute window limit
        if current_time - self.two_min_window_start >= 120:
            # Reset 2-minute window
            self.two_min_window_start = current_time
            self.requests_in_current_2min = 0
        
        # If we're approaching the 2-minute limit, wait
        if self.requests_in_current_2min >= REQUESTS_PER_2MIN:
            wait_time = 120 - (current_time - self.two_min_window_start)
            if wait_time > 0:
                print(f" Approaching 2-min rate limit, waiting {wait_time:.1f}s...")
                time.sleep(wait_time + 1)
                self.two_min_window_start = time.time()
                self.requests_in_current_2min = 0
        
        # Normal per-second delay
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    def make_api_request(self, url, params=None):
        """Make a rate-limited API request"""
        self.check_rate_limits()
        
        response = self.session.get(url, params=params)
        self.total_api_calls += 1
        self.requests_in_current_2min += 1
        
        return response
    
    def get_existing_match_count(self):
        """Count how many match files we already have"""
        if not os.path.exists(MATCHES_DIR):
            return 0
        return len([f for f in os.listdir(MATCHES_DIR) if f.endswith('.json')])
    
    def fetch_match_ids(self, puuid, start=5, count=20):
        """Fetch match IDs for a player"""
        url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        params = {
            "start": start,
            "count": count
        }
        
        if QUEUE_TYPE:
            params["queue"] = QUEUE_TYPE
            
        print(f"Fetching match IDs for {puuid[:20]}... (start={start}, count={count})")
        
        try:
            response = self.make_api_request(url, params)
            
            if response.status_code == 200:
                match_ids = response.json()
                print(f" Found {len(match_ids)} match IDs")
                return match_ids
            elif response.status_code == 429:
                print("Rate limited! Waiting 30s...")
                time.sleep(30)
                return self.fetch_match_ids(puuid, start, count)
            else:
                print(f" Error fetching match IDs: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f" Exception fetching match IDs: {e}")
            return []
    
    def fetch_match_data(self, match_id):
        """Fetch detailed match data"""
        url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
        
        try:
            response = self.make_api_request(url)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(" Rate limited! Waiting 30s...")
                time.sleep(30)
                return self.fetch_match_data(match_id)
            else:
                print(f"Error fetching match {match_id}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f" Exception fetching match {match_id}: {e}")
            return None
    
    def save_match_to_backend(self, match_data):
        """Save match data using the backend API"""
        try:
            response = requests.post(
                BACKEND_URL,
                headers={"Content-Type": "application/json"},
                json=match_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                return True, result.get("message", "Saved")
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, str(e)
    
    def process_player(self, puuid, names):
        """Process a single player - fetch and save their matches"""
        print(f"\n{'='*60}")
        print(f"Processing player: {names}")
        print(f"PUUID: {puuid}")
        print(f"{'='*60}")
        
        # Fetch match IDs
        match_ids = self.fetch_match_ids(puuid, count=MATCHES_PER_PLAYER)
        
        if not match_ids:
            print("No match IDs found, skipping player")
            return 0
            
        matches_saved_for_player = 0
        
        for i, match_id in enumerate(match_ids, 1):
            print(f"\n[{i}/{len(match_ids)}] Processing match: {match_id}")
            
            # Fetch match data (rate limiting handled in make_api_request)
            match_data = self.fetch_match_data(match_id)
            
            if match_data:
                # Save to backend
                success, message = self.save_match_to_backend(match_data)
                
                if success:
                    print(f"✓ {message}")
                    if "saved" in message.lower():
                        matches_saved_for_player += 1
                        self.total_matches_saved += 1
                else:
                    print(f"✗ Failed to save: {message}")
            else:
                print("✗ Failed to fetch match data")
        
        print(f"\nPlayer summary: {matches_saved_for_player} new matches saved")
        return matches_saved_for_player
    
    def run(self):
        """Main collection loop"""
        print("Starting Match Data Collector")
        
        # Check if we're using a specific PUUID
        if SPECIFIC_PUUID:
            print(f"Mode: SPECIFIC PUUID - {SPECIFIC_PUUID}")
            print(f"Will crawl {MATCHES_PER_PLAYER} matches for this player only")
        else:
            print(f"Mode: RANDOM PLAYERS - {MAX_ITERATIONS} players, {MATCHES_PER_PLAYER} matches each")
        
        print(f"Rate limit: {REQUESTS_PER_SECOND} req/sec, {REQUESTS_PER_2MIN} req/2min")
        print(f"Queue filter: {QUEUE_TYPE if QUEUE_TYPE else 'All queues'}")
        
        start_time = datetime.now()
        existing_matches = self.get_existing_match_count()
        print(f"Existing matches: {existing_matches}")
        
        # Handle specific PUUID mode
        if SPECIFIC_PUUID:
            print(f"\n{'#'*80}")
            print(f"PROCESSING SPECIFIC PLAYER")
            print(f"{'#'*80}")
            
            # Get player info for the specific PUUID
            puuid, names = self.get_specific_player_info(SPECIFIC_PUUID)
            
            # Process the specific player
            matches_saved = self.process_player(puuid, names)
            
            # Mark as processed
            self.processed_players.add(puuid)
            
            print(f"\n{'='*80}")
            print("SPECIFIC PLAYER COLLECTION COMPLETE!")
            print(f"Player: {names}")
            print(f"PUUID: {puuid}")
            print(f"Matches saved: {matches_saved}")
            print(f"Total API calls made: {self.total_api_calls}")
            print(f"Total time: {datetime.now() - start_time}")
            print(f"{'='*80}")
            
            return
        
        # Handle random players mode (original logic)
        for iteration in range(MAX_ITERATIONS):
            print(f"\n{'#'*80}")
            print(f"ITERATION {iteration + 1}/{MAX_ITERATIONS}")
            print(f"{'#'*80}")
            
            # Get a random player
            puuid, names = self.get_random_player_with_low_matches()
            
            if not puuid:
                print("No more players to process!")
                break
                
            # Process the player
            matches_saved = self.process_player(puuid, names)
            
            # Mark as processed
            self.processed_players.add(puuid)
            
            # Progress summary
            elapsed = datetime.now() - start_time
            print(f"\n--- PROGRESS SUMMARY ---")
            print(f"Iteration: {iteration + 1}/{MAX_ITERATIONS}")
            print(f"Players processed: {len(self.processed_players)}")
            print(f"Total matches saved: {self.total_matches_saved}")
            print(f"Total API calls: {self.total_api_calls}")
            print(f"Time elapsed: {elapsed}")
            print(f"Average matches per player: {self.total_matches_saved / len(self.processed_players):.1f}")
            
            # Small break between players
            if iteration < MAX_ITERATIONS - 1:
                print(f"\nWaiting before next player...")
                time.sleep(2)
        
        print(f"\n{'='*80}")
        print("COLLECTION COMPLETE!")
        print(f"Total players processed: {len(self.processed_players)}")
        print(f"Total matches saved: {self.total_matches_saved}")
        print(f"Total API calls made: {self.total_api_calls}")
        print(f"Total time: {datetime.now() - start_time}")
        print(f"{'='*80}")

if __name__ == "__main__":
    if API_KEY == "YOUR_RIOT_API_KEY_HERE":
        print("ERROR: Please set your Riot API key in the API_KEY variable!")
        exit(1)
        
    collector = MatchCollector()
    
    try:
        collector.run()
    except KeyboardInterrupt:
        print(f"\n\nCollection stopped by user!")
        print(f"Matches saved so far: {collector.total_matches_saved}")
        print(f"API calls made: {collector.total_api_calls}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print(f"Matches saved so far: {collector.total_matches_saved}")
        print(f"API calls made: {collector.total_api_calls}")
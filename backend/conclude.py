import sqlite3
import json
import os
from statistics import mean
from collections import defaultdict
from dotenv import load_dotenv

def analyze_country_performance(db_path):
    """
    Analyze player performance by country from SQLite database.
    
    Args:
        db_path (str): Path to the SQLite database file
    """
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print('Connected . . .')
    query = """
    SELECT puuid, names, feedscore, opscore, country, match_count 
    FROM players 
    WHERE country IS NOT NULL AND country != ''
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    country_data = defaultdict(list)
    
    for row in rows:
        puuid, names, feedscore, opscore, country, match_count = row
        if feedscore is None or opscore is None:
            continue
            
        country_data[country].append({
            'puuid': puuid,
            'names': names,
            'feedscore': feedscore,
            'opscore': opscore,
            'match_count': match_count
        })
    country_stats = {}
    
    for country, players in country_data.items():
        if not players:
            continue
            
        feedscores = [p['feedscore'] for p in players]
        opscores = [p['opscore'] for p in players]
        
        country_stats[country] = {
            'player_count': len(players),
            'avg_feedscore': mean(feedscores),
            'avg_opscore': mean(opscores),
            'total_matches': sum(p['match_count'] for p in players if p['match_count']),
            'players': players
        }
    
    return country_stats

def display_results(country_stats):
    """Display the analysis results."""
    
    print("=" * 80)
    print("COUNTRY PERFORMANCE ANALYSIS")
    print("=" * 80)
    sorted_by_opscore = sorted(
        country_stats.items(), 
        key=lambda x: x[1]['avg_opscore'], 
        reverse=True
    )
    sorted_by_feedscore = sorted(
        country_stats.items(), 
        key=lambda x: x[1]['avg_feedscore']
    )
    
    print(f"\n📊 SUMMARY STATISTICS")
    print(f"Total countries analyzed: {len(country_stats)}")
    print(f"Total players: {sum(stats['player_count'] for stats in country_stats.values())}")
    print(f"Total matches: {sum(stats['total_matches'] for stats in country_stats.values())}")
    
    print(f"\n🏆 TOP 10 COUNTRIES BY OPSCORE (Higher is Better)")
    print("-" * 80)
    print(f"{'Rank':<4} {'Country':<20} {'Players':<8} {'Avg OpScore':<12} {'Avg FeedScore':<13} {'Total Matches'}")
    print("-" * 80)
    
    for i, (country, stats) in enumerate(sorted_by_opscore[:10], 1):
        print(f"{i:<4} {country:<20} {stats['player_count']:<8} "
              f"{stats['avg_opscore']:<12.2f} {stats['avg_feedscore']:<13.2f} {stats['total_matches']}")
    
    print(f"\n🥇 BEST PERFORMING COUNTRIES BY FEEDSCORE (Lower is Better)")
    print("-" * 80)
    print(f"{'Rank':<4} {'Country':<20} {'Players':<8} {'Avg FeedScore':<13} {'Avg OpScore':<12} {'Total Matches'}")
    print("-" * 80)
    
    for i, (country, stats) in enumerate(sorted_by_feedscore[:10], 1):
        print(f"{i:<4} {country:<20} {stats['player_count']:<8} "
              f"{stats['avg_feedscore']:<13.2f} {stats['avg_opscore']:<12.2f} {stats['total_matches']}")
    
    print(f"\n🔻 WORST PERFORMING COUNTRIES BY OPSCORE")
    print("-" * 80)
    print(f"{'Rank':<4} {'Country':<20} {'Players':<8} {'Avg OpScore':<12} {'Avg FeedScore':<13} {'Total Matches'}")
    print("-" * 80)
    
    for i, (country, stats) in enumerate(reversed(sorted_by_opscore[-10:]), 1):
        print(f"{i:<4} {country:<20} {stats['player_count']:<8} "
              f"{stats['avg_opscore']:<12.2f} {stats['avg_feedscore']:<13.2f} {stats['total_matches']}")
    
    print(f"\n🔻 WORST PERFORMING COUNTRIES BY FEEDSCORE (Higher is Worse)")
    print("-" * 80)
    print(f"{'Rank':<4} {'Country':<20} {'Players':<8} {'Avg FeedScore':<13} {'Avg OpScore':<12} {'Total Matches'}")
    print("-" * 80)
    
    for i, (country, stats) in enumerate(reversed(sorted_by_feedscore[-10:]), 1):
        print(f"{i:<4} {country:<20} {stats['player_count']:<8} "
              f"{stats['avg_feedscore']:<13.2f} {stats['avg_opscore']:<12.2f} {stats['total_matches']}")

def show_country_details(country_stats, country_name):
    """Show detailed information for a specific country."""
    
    if country_name not in country_stats:
        print(f"Country '{country_name}' not found in database.")
        return
    
    stats = country_stats[country_name]
    print(f"\n🔍 DETAILED VIEW: {country_name}")
    print("=" * 60)
    print(f"Total Players: {stats['player_count']}")
    print(f"Average OpScore: {stats['avg_opscore']:.2f}")
    print(f"Average FeedScore: {stats['avg_feedscore']:.2f}")
    print(f"Total Matches: {stats['total_matches']}")
    
    print(f"\nTop 10 Players:")
    print("-" * 60)
    sorted_players = sorted(stats['players'], key=lambda x: x['opscore'], reverse=True)
    
    for i, player in enumerate(sorted_players[:10], 1):
        names = json.loads(player['names']) if isinstance(player['names'], str) else player['names']
        name_str = names[0] if names else "Unknown"
        print(f"{i:2}. {name_str:<25} OpScore: {player['opscore']:8.2f} FeedScore: {player['feedscore']:8.2f}")

def main():
    load_dotenv()
    
    # Get database path from environment variable
    db_path = os.getenv('DB_PATH')
    
    if not db_path:
        print("Error: DB_PATH not found in .env file.")
        print("Please create a .env file with: DB_PATH=path/to/your/database.db")
        return
    
    try:
        print("Analyzing player performance by country...")
        country_stats = analyze_country_performance(db_path)
        
        if not country_stats:
            print("No data found or database is empty.")
            return
        
        display_results(country_stats)
        while True:
            print(f"\n" + "="*80)
            user_input = input("Enter a country name to see details (or 'quit' to exit): ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            elif user_input:
                show_country_details(country_stats, user_input)
        
        print("\nAnalysis complete!")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except FileNotFoundError:
        print(f"Database file '{db_path}' not found. Please check the path.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
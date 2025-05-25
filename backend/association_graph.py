import json
import os
import sqlite3
import networkx as nx
from pyvis.network import Network
import sys

# === CONFIG ===
MATCH_FOLDER = "./data"      # Folder with EUN1_*.json files
DB_PATH = "../playersrefined.db"       # Path to your SQLite database 
OUTPUT_HTML = "output/premade_network.html"

# === Load match data ===
def load_matches_from_folder(folder_path):
    matches = []
    for filename in os.listdir(folder_path):
        if filename.startswith("EUN1_") and filename.endswith(".json"):
            with open(os.path.join(folder_path, filename), 'r', encoding='utf-8') as file:
                try:
                    data = json.load(file)
                    matches.append(data)
                except json.JSONDecodeError:
                    print(f"Failed to load {filename}")
    return matches

# === Build association graph ===
def add_match_to_graph(G, match_data):
    try:
        # We use puuid here as the node id
        puuids = [p["puuid"] for p in match_data["info"]["participants"]]
    except KeyError:
        return  # Skip broken matches

    for i, p1 in enumerate(puuids):
        for j in range(i + 1, len(puuids)):
            p2 = puuids[j]
            if G.has_edge(p1, p2):
                G[p1][p2]['weight'] += 1
            else:
                G.add_edge(p1, p2, weight=1)

# === Get latest name from names string ===
def get_latest_name(names_str):
    if not names_str:
        return "Unknown#Unknown"
    
    try:
        # Parse the JSON string to get the list of names
        names_list = json.loads(names_str)
        
        # Check if it's actually a list and not empty
        if isinstance(names_list, list) and len(names_list) > 0:
            latest_name = names_list[-1].strip()
            return latest_name if latest_name else "Unknown#Unknown"
        else:
            return "Unknown#Unknown"
            
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        print(f"Error parsing names field: {names_str} - Error: {e}")
        return "Unknown#Unknown"

# === Enrich nodes with player stats ===
def add_player_stats_to_graph(G, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for node in G.nodes():
        cursor.execute("SELECT names, feedscore, opscore FROM players WHERE puuid = ?", (node,))
        row = cursor.fetchone()
        if row:
            latest_name = get_latest_name(row[0])
            feedscore = row[1]
            opscore = row[2]
            G.nodes[node]["label_name"] = latest_name
            G.nodes[node]["feedscore"] = feedscore
            G.nodes[node]["opscore"] = opscore
        else:
            G.nodes[node]["label_name"] = "Unknown#Unknown"
            G.nodes[node]["feedscore"] = "N/A"
            G.nodes[node]["opscore"] = "N/A"

    conn.close()

# === Visualize graph ===
def visualize_graph(G, output_html="premade_network.html"):
    net = Network(notebook=False, height="800px", width="100%", bgcolor="#222222", font_color="white")
    net.barnes_hut()

    for node, data in G.nodes(data=True):
        label = f"{data.get('label_name', 'Unknown#Unknown')}\nFeedscore:{data.get('feedscore', 'N/A')}\nOpscore:{data.get('opscore', 'N/A')}"
        net.add_node(node, label=label, title=label)

    for source, target, data in G.edges(data=True):
        weight = data.get("weight", 1)
        if weight >= 3:  # Only show edges with at least 3 matches together
            net.add_edge(source, target, value=weight, title=f"Matches: {weight}")

    net.write_html(output_html, notebook=False, open_browser=False)

# === Main ===
if __name__ == "__main__":
    G = nx.Graph()

    print("Loading matches...")
    matches = load_matches_from_folder(MATCH_FOLDER)

    print("Building graph...")
    for match in matches:
        add_match_to_graph(G, match)

    print("Adding player stats...")
    add_player_stats_to_graph(G, DB_PATH)

    print("Generating visualization...")
    visualize_graph(G, OUTPUT_HTML)

    print(f"Graph saved to {OUTPUT_HTML}")
    sys.exit(0)
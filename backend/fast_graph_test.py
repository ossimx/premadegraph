import json
import os
import sqlite3
import networkx as nx
from pyvis.network import Network
import sys
import argparse

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
        names_list = json.loads(names_str)
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

# === Filter standalone nodes ===
def filter_connected_nodes(G, min_edge_weight=3):
    """
    Create a subgraph containing only nodes that have at least one edge
    with weight >= min_edge_weight
    """
    connected_nodes = set()
    
    for source, target, data in G.edges(data=True):
        weight = data.get("weight", 1)
        if weight >= min_edge_weight:
            connected_nodes.add(source)
            connected_nodes.add(target)
    
    return G.subgraph(connected_nodes).copy()

# === Visualize graph ===
def visualize_graph(G, output_html="premade_network.html", show_standalone=True, min_edge_weight=3):
    """
    Visualize the graph with option to hide standalone nodes
    
    Args:
        G: NetworkX graph
        output_html: Output file path
        show_standalone: If False, only show nodes with connections >= min_edge_weight
        min_edge_weight: Minimum edge weight to display
    """
    # Filter graph if requested
    if not show_standalone:
        G_viz = filter_connected_nodes(G, min_edge_weight)
        print(f"Filtered graph: {len(G_viz.nodes())} connected nodes (from {len(G.nodes())} total)")
    else:
        G_viz = G
        print(f"Full graph: {len(G_viz.nodes())} nodes")
    
    net = Network(notebook=False, height="800px", width="100%", bgcolor="#222222", font_color="white")
    
    # Configure physics for large networks - orbital layout around center
    net.set_options("""
    var options = {
        "physics": {
            "enabled": true,
            "stabilization": {
                "enabled": true,
                "iterations": 300,
                "updateInterval": 25
            },
            "barnesHut": {
                "gravitationalConstant": -12000,
                "centralGravity": 0.8,
                "springLength": 150,
                "springConstant": 0.02,
                "damping": 0.09,
                "avoidOverlap": 0.2
            }
        },
        "interaction": {
            "dragNodes": true,
            "dragView": true,
            "zoomView": true
        }
    }
    """)

    # Add nodes
    for node, data in G_viz.nodes(data=True):
        label = f"{data.get('label_name', 'Unknown#Unknown')}\nFeedscore:{data.get('feedscore', 'N/A')}\nOpscore:{data.get('opscore', 'N/A')}"
        net.add_node(node, label=label, title=label)

    # Add edges
    edges_added = 0
    for source, target, data in G_viz.edges(data=True):
        weight = data.get("weight", 1)
        if weight >= min_edge_weight:
            net.add_edge(source, target, value=weight, title=f"Matches: {weight}")
            edges_added += 1
    
    print(f"Added {edges_added} edges with weight >= {min_edge_weight}")
    
    html_template = """
    <html>
    <head>
        <meta charset="utf-8">
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/vis-network.min.js"></script>
        <style type="text/css">
            #mynetworkid {
                width: 100%;
                height: 800px;
                background-color: #222222;
                border: 1px solid lightgray;
                position: relative;
            }
            .controls {
                position: absolute;
                top: 10px;
                left: 10px;
                z-index: 1000;
                background: rgba(0,0,0,0.8);
                padding: 10px;
                border-radius: 5px;
                color: white;
            }
            .controls button {
                margin: 5px;
                padding: 5px 10px;
                background: #444;
                color: white;
                border: none;
                border-radius: 3px;
                cursor: pointer;
            }
            .controls button:hover {
                background: #666;
            }
            .controls button.active {
                background: #007acc;
            }
        </style>
    </head>
    <body>
        <div class="controls">
            <div>View Mode:</div>
            <button id="showAll" onclick="toggleMode('all')" class="active">Show All Nodes</button>
            <button id="showConnected" onclick="toggleMode('connected')">Connected Only</button>
            <div style="margin-top: 10px; font-size: 12px;">
                Min Edge Weight: <input type="number" id="minWeight" value="3" min="1" max="10" onchange="updateMinWeight()">
            </div>
        </div>
        <div id="mynetworkid"></div>
        
        <script type="text/javascript">
            // This will be replaced with actual data
            var nodes = new vis.DataSet(NODES_DATA);
            var edges = new vis.DataSet(EDGES_DATA);
            var allNodes = nodes.get();
            var allEdges = edges.get();
            var currentMinWeight = 3;
            var currentMode = 'all';
            
            var container = document.getElementById('mynetworkid');
            var data = { nodes: nodes, edges: edges };
            var options = {
                physics: {
                    enabled: true,
                    stabilization: {
                        enabled: true,
                        iterations: 300,
                        updateInterval: 25
                    },
                    barnesHut: {
                        gravitationalConstant: -12000,
                        centralGravity: 0.8,
                        springLength: 150,
                        springConstant: 0.02,
                        damping: 0.09,
                        avoidOverlap: 0.2
                    }
                },
                interaction: {
                    dragNodes: true,
                    dragView: true,
                    zoomView: true
                },
                nodes: {
                    borderWidth: 2,
                    size: 15,
                    color: {
                        border: '#222222',
                        background: '#666666'
                    },
                    font: { color: '#eeeeee', size: 12 }
                },
                edges: {
                    color: 'lightgray',
                    width: 1
                }
            };
            var network = new vis.Network(container, data, options);
            
            function toggleMode(mode) {
                currentMode = mode;
                updateVisualization();
                
                // Update button states
                document.getElementById('showAll').classList.toggle('active', mode === 'all');
                document.getElementById('showConnected').classList.toggle('active', mode === 'connected');
            }
            
            function updateMinWeight() {
                currentMinWeight = parseInt(document.getElementById('minWeight').value);
                updateVisualization();
            }
            
            function updateVisualization() {
                // Filter edges by weight
                var filteredEdges = allEdges.filter(function(edge) {
                    return edge.value >= currentMinWeight;
                });
                
                var nodesToShow;
                if (currentMode === 'connected') {
                    // Get nodes that have at least one edge with sufficient weight
                    var connectedNodeIds = new Set();
                    filteredEdges.forEach(function(edge) {
                        connectedNodeIds.add(edge.from);
                        connectedNodeIds.add(edge.to);
                    });
                    nodesToShow = allNodes.filter(function(node) {
                        return connectedNodeIds.has(node.id);
                    });
                } else {
                    nodesToShow = allNodes;
                }
                
                // Update the visualization
                nodes.clear();
                edges.clear();
                nodes.add(nodesToShow);
                edges.add(filteredEdges);
            }
        </script>
    </body>
    </html>
    """
    net.write_html(output_html, notebook=False)

    with open(output_html, 'r', encoding='utf-8') as f:
        html_content = f.read()
    import re
    nodes_match = re.search(r'var nodes = new vis\.DataSet\((.*?)\);', html_content, re.DOTALL)
    edges_match = re.search(r'var edges = new vis\.DataSet\((.*?)\);', html_content, re.DOTALL)
    options_match = re.search(r'var options = ({.*?});', html_content, re.DOTALL)
    
    if nodes_match and edges_match and options_match:
        nodes_data = nodes_match.group(1)
        edges_data = edges_match.group(1)
        options_data = options_match.group(1)
        final_html = html_template.replace('NODES_DATA', nodes_data)
        final_html = final_html.replace('EDGES_DATA', edges_data)
        final_html = final_html.replace('OPTIONS_DATA', options_data)
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(final_html)

# === Main ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate network visualization of player connections')
    parser.add_argument('--connected-only', action='store_true', 
                       help='Show only connected nodes (hide standalone nodes)')
    parser.add_argument('--min-weight', type=int, default=3,
                       help='Minimum edge weight to display (default: 3)')
    
    args = parser.parse_args()
    
    G = nx.Graph()

    print("Loading matches...")
    matches = load_matches_from_folder(MATCH_FOLDER)

    print("Building graph...")
    for match in matches:
        add_match_to_graph(G, match)

    print("Adding player stats...")
    add_player_stats_to_graph(G, DB_PATH)

    print("Generating visualization...")
    visualize_graph(G, OUTPUT_HTML, 
                   show_standalone=not args.connected_only, 
                   min_edge_weight=args.min_weight)

    print(f"Graph saved to {OUTPUT_HTML}")
    
    # Print some statistics
    total_nodes = len(G.nodes())
    connected_nodes = len(filter_connected_nodes(G, args.min_weight).nodes())
    standalone_nodes = total_nodes - connected_nodes
    
    print(f"\nGraph Statistics:")
    print(f"Total nodes: {total_nodes}")
    print(f"Connected nodes (with edges >= {args.min_weight}): {connected_nodes}")
    print(f"Standalone nodes: {standalone_nodes}")
    
    sys.exit(0)
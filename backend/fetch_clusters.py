import json
import sqlite3
import os

def fetch_cluster_names_with_puuids(cluster_json_path, db_path, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(cluster_json_path, 'r', encoding='utf-8') as f:
        clusters_data = json.load(f)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {"clusters": []}

    for cluster in clusters_data["clusters"]:
        members = cluster["members"]
        names = []
        for puuid in members:
            cursor.execute("SELECT names FROM players WHERE puuid = ?", (puuid,))
            row = cursor.fetchone()
            if row:
                try:
                    stored_names = json.loads(row[0])
                    if isinstance(stored_names, list) and len(stored_names) > 0:
                        names.append(stored_names[-1])
                    elif isinstance(stored_names, str):
                        names.append(stored_names)
                    else:
                        names.append("unknown")
                except json.JSONDecodeError:
                    names.append("unknown")
            else:
                names.append("unknown")

        result["clusters"].append({
            "members": members,
            "names": names,
            **{k: v for k, v in cluster.items() if k not in ["members"]}
        })

    conn.close()

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

# Run
fetch_cluster_names_with_puuids(
    cluster_json_path='clusters/clusters.json',
    db_path='../playersrefined.db',
    output_path='clusters/clusters_with_names.json'
)

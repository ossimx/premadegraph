import requests
import json
import time
import os
import sqlite3
import re
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "google/gemini-2.0-flash-001"
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "X-Title": "lol-cluster-country-detector"
}

def load_clusters_with_names(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["clusters"]

def batch_clusters(clusters, batch_size):
    for i in range(0, len(clusters), batch_size):
        yield clusters[i:i + batch_size]

def build_prompt_for_clusters(cluster_batch):
    prompt_lines = [
        "You will receive a list of clusters, each cluster has multiple player names separated by commas.",
        "Analyze the names in each cluster and return a JSON object where keys are cluster IDs (e.g. cluster1) and values are the most likely country of origin for that entire cluster.",
        "Clusters are from Eastern/Nordic Europe  or the Middle East (EUNE region).If a name looks too foreign try to look for clues in the batch, try to reason.",
        "Excluded Countries(because they have their own region) : Turkey,Russia,Western Europe",
        "Only return the JSON object.",
        "The content is expected to be a JSON string like:",
        '{ "cluster1": "Poland", "cluster2": "Greece" }',
        ""
    ]
    
    for idx, cluster in enumerate(cluster_batch, start=1):
        cluster_id = f"cluster{idx}"
        names_str = ", ".join(cluster.get("names", []))
        prompt_lines.append(f"{cluster_id}: {names_str}")

    return "\n".join(prompt_lines)

def call_openrouter_api(prompt):
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=HEADERS,
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"API call failed: {e}")
        return None

def parse_ai_response(response_content):
    try:
        match = re.search(r"\{\s*\"cluster\d+\".*?\}", response_content, re.DOTALL)
        if not match:
            print("No valid JSON block found in AI response.")
            return None
        json_str = match.group(0)
        return json.loads(json_str)
    except Exception as e:
        print(f"Failed to parse AI response JSON: {e}")
        return None

def update_countries_in_db(db_path, clusters_batch, cluster_country_map):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for idx, cluster in enumerate(clusters_batch, start=1):
        cluster_id = f"cluster{idx}"
        country = cluster_country_map.get(cluster_id)
        if not country:
            print(f"No country found for {cluster_id}, skipping DB update")
            continue
        
        for puuid in cluster.get("members", []):
            cursor.execute("UPDATE players SET country = ? WHERE puuid = ?", (country, puuid))
    
    conn.commit()
    conn.close()

def main():
    clusters = load_clusters_with_names("clusters/clusters_with_names.json")
    batch_size = 3
    
    for cluster_batch in batch_clusters(clusters, batch_size):
        prompt = build_prompt_for_clusters(cluster_batch)
        print("Sending prompt:\n", prompt)
        
        response_json = call_openrouter_api(prompt)
        if response_json is None:
            print("Skipping this batch due to API error.")
            continue
        
        ai_content = response_json["choices"][0]["message"]["content"]
        
        # Log AI response for debugging
        with open("ai_responses.log", "a", encoding="utf-8") as log_file:
            log_file.write("Prompt:\n" + prompt + "\n")
            log_file.write("Response:\n" + ai_content + "\n\n")
        
        cluster_country_map = parse_ai_response(ai_content)
        if cluster_country_map is None:
            print("Skipping this batch due to parsing error.")
            continue
        
        update_countries_in_db(DB_PATH, cluster_batch, cluster_country_map)
        print(f"Updated DB for batch with {len(cluster_batch)} clusters.")
        
        time.sleep(5)  # to avoid rate limits or spamming the API

if __name__ == "__main__":
    main()

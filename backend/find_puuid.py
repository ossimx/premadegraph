import os
import json
import glob

def find_matches_with_puuid(directory, target_puuid):
    matches_found = []

    # Find all .json files in the directory (recursively)
    json_files = glob.glob(os.path.join(directory, '**', '*.json'), recursive=True)

    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

                participants = data.get('metadata', {}).get('participants', [])
                match_id = data.get('metadata', {}).get('matchId', 'Unknown ID')

                if target_puuid in participants:
                    print(f"[FOUND] Match ID: {match_id} | File: {filepath}")
                    matches_found.append((match_id, filepath))

        except Exception as e:
            print(f"[ERROR] Failed to process {filepath}: {e}")

    print(f"\nDone. Found {len(matches_found)} matches containing PUUID: {target_puuid}")
    return matches_found


# === CONFIGURATION ===
if __name__ == '__main__':
    match_dir = './data'  # Change to your match history directory
    puuid_to_search = 'qGP42qa5eJe6JKundM8znIMDTiaDs_G8venP8i1Jn8joOQxSbH83Fop6kOtHYeJrZlUPPHcBj_ETOg'  # Replace with the actual puuid

    find_matches_with_puuid(match_dir, puuid_to_search)

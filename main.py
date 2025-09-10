import requests
import asyncio
import aiohttp
import json
import ast
import random
from datetime import datetime
import re
from tqdm import tqdm


scrape_protection_detected = False

async def collect_data_from_videoIds(videoIds, videoIds_dict, playlistIds_dict, cancel=True):
    global scrape_protection_detected

    games = []

    #connector=aiohttp.TCPConnector(limit=len(videoIds))
    async with aiohttp.ClientSession() as session:
        tasks = get_game_tasks(session, videoIds)
        with tqdm(total=len(videoIds), desc="Processing Videos", leave=False) as probar:
            for future in asyncio.as_completed(tasks):
                response = await future
                try:
                    snippet = await response.text(encoding='utf-8')
                    if scrape_protection_detected:
                        continue

                    url = str(response.request_info.url)
                    videoIdIdx = url.find("watch?v=") + len("watch?v=")
                    videoId = url[videoIdIdx:videoIdIdx+11]
                    playlistId = videoIds_dict[videoId]
                    playlist_number = playlistIds_dict[playlistId]["playlist_number"]
                    index = playlistIds_dict[playlistId]["index"]
                    if index == -1:
                        index = playlistIds_dict["Supercup"]["videoIds"].index(videoId)

                    league, season = get_league_season(playlist_number, index)
                    
                    game = collect_scrape_protection(snippet, league, season, playlistId)
                    game["video_id"] = videoId
                    games.append(game)
                except Exception as e:
                    if cancel:
                        scrape_protection_detected = True
                    tqdm.write(f"Timeout, skipping video: {videoId}, [{e}]")
                finally:
                    probar.update(1)

        return games


def get_game_tasks(session, videoIds):
    tasks = []
    for videoId in videoIds:
        tasks.append(asyncio.create_task(session.get("https://www.youtube.com/watch?v=" + videoId, ssl=False)))
    return tasks


def parse_playlist_string(playlist_string):
    line = playlist_string.split(",")
    playlist_id = line[0]
    avoid = []
    length = 9
    if len(line) == 2:
        avoid = [int(line[1])]
    elif len(line) > 2:
        length = int(line[-1])
        if line[1] != "":
            for a in line[1:-1]:
                avoid.append(int(a))

    return playlist_id, length, tuple(avoid)


def get_synonyms():
    with open("jsonfiles/synonyms.json", "r", encoding="utf-8") as json_file:
        return json.load(json_file)


def get_videoIds_from_playlistId(playlistId, length, avoid):
    q = "https://www.youtube.com/playlist?list=" + playlistId
    response = requests.get(q)
    snippet = response.text
    snippet = snippet[snippet.find("""thumbnail":{"thumbnails":[{"url"""):]
    snippet = snippet[snippet.find("""{"label":"""):]

    videoIds = []
    for idx in range(length):
        videoIdx = idx + 1
        if videoIdx in avoid:
            snippet = snippet[snippet.find("""thumbnail":{"thumbnails":[{"url"""):]
            snippet = snippet[snippet.find("""{"label":"""):]
            continue

        snippet = snippet[snippet.find("videoId") + len("videoId") + 3:]
        videoId = snippet[:11]
        videoIds.append(videoId)

        snippet = snippet[snippet.find("""thumbnail":{"thumbnails":[{"url"""):]
        snippet = snippet[snippet.find("""{"label":"""):]

    return videoIds

def collect_scrape_protection(snippet, league, season, playlist_id=None):
    find = """{"title":{"runs":[{"text":"""
    snippet = snippet[snippet.find(find):]

    bracketsOpen = 0
    for idx, character in enumerate(snippet):
        if character == "{":
            bracketsOpen += 1
        elif character == "}":
            bracketsOpen -= 1
        if bracketsOpen == 0:
            snippet = snippet[:idx+1]
            break
    
    snippet = snippet.replace("true", "True")
    snippet = snippet.replace("false", "False")
    videoDetails = ast.literal_eval(snippet)

    game = dict()
    #game["videoId"] = videoDetails["flexibleItems"][0]["menuFlexibleItemRenderer"]["menuItem"]["menuServiceItemRenderer"]["serviceEndpoint"]["modalEndpoint"]["modal"]["modalWithTitleAndButtonRenderer"]["button"]["buttonRenderer"]["navigationEndpoint"]["signInEndpoint"]["nextEndpoint"]["watchEndpoint"]["videoId"]
    game["title"] = videoDetails["title"]["runs"][0]["text"]

    home_team, away_team = get_home_away_team(game["title"])
    game["home_team"] = home_team
    game["away_team"] = away_team

    views = videoDetails["viewCount"]["videoViewCountRenderer"]["viewCount"]["simpleText"]
    views = views[:views.find(" ")]
    game["int_views"] = int(views.replace(".", ""))
    
    try:
        date = videoDetails["dateText"]["simpleText"]
        game["date"] = re.search(r"\d{2}\.\d{2}\.\d{4}", date).group(0)
        game["upload_d"] = (datetime.now().date() - datetime.strptime(game["date"], "%d.%m.%Y").date()).days
    except Exception as e:
        with open("scrape_date.json", "w", encoding="utf-8") as json_file:
            json.dump(videoDetails, json_file, indent=2)
        raise Exception(e)
        

    game["competition"] = league
    game["season"] = season
    game["playlist_id"] = playlist_id

    return game



def get_synonym(team, synonyms):
    for real_team in synonyms:
        synonym = synonyms[real_team]
        if team in synonym:
            return real_team
    else:
        print(f"{team} not found")
        return None
    
def get_home_away_team(title):
    if title is None:
        return

    synonyms = get_synonyms()

    title = title.replace("\u202F", " ")
    highlight_check = title[:title.find("Highlights")]
    if highlight_check.find("|") == -1:
        title = title[:title.find("Highlights") - 1]
    else:
        title = title[:title.find("|") - 1]
    vs_idx = title.find(" - ")
    if vs_idx == -1:
        vs_idx = title.find(" – ")
    team1 = title[:vs_idx]
    team2 = title[vs_idx + 3:]

    while team1[-1] == " ":
        team1 = team1[:-1]
    while team2[-1] == " ":
        team2 = team2[:-1]

    home_team = None
    away_team = None
    for team in synonyms:
        synonym = synonyms[team]
        if team1 in synonym:
            home_team = team
            break
    else:
        tqdm.write(team1)  # print debug
        tqdm.write(title)
    for team in synonyms:
        synonym = synonyms[team]
        if team2 in synonym:
            away_team = team
            break
    else:
        tqdm.write(team2)  # print debug
        tqdm.write(title)

    if home_team is None or away_team is None:
        raise Exception("Synonym Missing")

    return home_team, away_team


def get_urls_from_txt(playlist_number):
    urls = []
    match playlist_number:
        case 0:
            with open("playlists/Season2122.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case 1:
            with open("playlists/Season2223.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case 2:
            with open("playlists/Season2324.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case 3:
            with open("playlists/2Bundesliga.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case 4:
            with open("playlists/DFBPokal.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case 5:
            with open("playlists/Relegation.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case 6:
            with open("playlists/Season2425.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case 7:
            with open("playlists/Season2526.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
        case _:
            urls = []
    return urls


def get_league_season(playlist_number, idx):
    league = None
    season = None
    match playlist_number:
        case -1:
            league = "DFL-Supercup"
            match idx:
                case 0:
                    season = "2021/22"
                case 1:
                    season = "2022/23"
                case 2:
                    season = "2023/24"
                case 3:
                    season = "2024/25"
                case 4:
                    season = "2025/26"
        case 0:
            league = "Bundesliga"
            season = "2021/22"
        case 1:
            league = "Bundesliga"
            season = "2022/23"
        case 2:
            league = "Bundesliga"
            season = "2023/24"
        case 3:
            league = "2. Bundesliga"
            match idx:
                case 0:
                    season = "2021/22"
                case 1:
                    season = "2022/23"
                case 2:
                    season = "2023/24"
                case 3:
                    season = "2024/25"
                case 4:
                    season = "2025/26"
        case 4:
            league = "DFB-Pokal"
            match idx:
                case 0:
                    season = "2022/23"
                case 1:
                    season = "2023/24"
                case 2:
                    season = "2024/25"
                case 3:
                    season = "2025/26"
        case 5:
            league = "Relegation"
            match idx:
                case 0:
                    season = "2021/22"
                case 1:
                    season = "2022/23"
                case 2:
                    season = "2023/24"
                case 3:
                    season = "2024/25"
                case 4:
                    season = "2025/26"
        case 6:
            league = "Bundesliga"
            season = "2024/25"
        case 7:
            league = "Bundesliga"
            season = "2025/26"
    return league, season


# MAIN FUNCTIONS
def update_jsonfiles(playlists_numbers=None):
    playlist_dict = dict()
    videoIds_dict = dict()
    
    p_numbers = range(8)
    if playlists_numbers is not None:
        p_numbers = playlists_numbers
    for playlist_number in p_numbers:
        print(f"Playlist Group {playlist_number + 1}/{len(p_numbers)}")
        urls = get_urls_from_txt(playlist_number)

        for idx, url in enumerate(urls):
            print(f"Playlist {idx + 1}/{len(urls)}")
            playlist_id, length, avoid = parse_playlist_string(url)
            videoIds = get_videoIds_from_playlistId(playlist_id, length, avoid)
            playlist_dict[playlist_id] = dict()
            playlist_dict[playlist_id]["playlist_number"] = playlist_number
            playlist_dict[playlist_id]["index"] = idx
            playlist_dict[playlist_id]["videoIds"] = videoIds

            for videoId in videoIds:
                videoIds_dict[videoId] = playlist_id

    with open("playlists/Supercup_games.txt", "r") as file:
        f = file.readlines()
        videoIds = []
        for line in f:
            videoIds.append(line.strip())

        mock_playlist_id = "Supercup"
        playlist_dict[mock_playlist_id] = dict()
        playlist_dict[mock_playlist_id]["videoIds"] = []
        for idx, videoId in enumerate(videoIds):
            videoIds_dict[videoId] = mock_playlist_id
            playlist_dict[mock_playlist_id]["playlist_number"] = -1
            playlist_dict[mock_playlist_id]["index"] = -1
            playlist_dict[mock_playlist_id]["videoIds"].append(videoId)
    
    videoIds_data = videoIds_dict
    if playlists_numbers is not None:
        with open("jsonfiles/videoId_to_playlistId.json", "r", encoding="utf-8") as json_file:
            videoIds_data = json.load(json_file)
            for vId in videoIds_dict:
                videoIds_data[vId] = videoIds_dict[vId]
    
    playlist_data = playlist_dict
    if playlists_numbers is not None:
        with open("jsonfiles/playlistIds.json", "r", encoding="utf-8") as json_file:
            playlist_data = json.load(json_file)
            for pId in playlist_dict:
                playlist_data[pId] = playlist_dict[pId]
    
    videoIds_json = json.dumps(videoIds_data, indent=3)
    with open("jsonfiles/videoId_to_playlistId.json", "w") as json_file:
        json_file.write(videoIds_json)

    playlist_ids_json = json.dumps(playlist_data, indent=3)
    with open("jsonfiles/playlistIds.json", "w") as json_file:
        json_file.write(playlist_ids_json)
        



def create_games_json_file(searchIds=None, cancel=True):
    games = []

    with open("jsonfiles/videoId_to_playlistId.json", "r") as videoIds_json_file, open("jsonfiles/playlistIds.json",
                                                                             "r") as playlist_ids_json_file:
        videoIds_dict = json.load(videoIds_json_file)
        playlistIds_dict = json.load(playlist_ids_json_file)
        videoIds = list(videoIds_dict.keys())

        usedIds = searchIds if searchIds is not None else videoIds
        usedIds.reverse()

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asynchrounous_calls_at_a_time = 100 #max 100

        with tqdm(total=len(usedIds), desc="Processing Chunks") as pbar:
            x = 1
            while asynchrounous_calls_at_a_time * x <= len(usedIds) and not scrape_protection_detected:
                games += asyncio.run(
                collect_data_from_videoIds(usedIds[(x - 1) * asynchrounous_calls_at_a_time:asynchrounous_calls_at_a_time * x], videoIds_dict, playlistIds_dict, cancel=cancel))

                x += 1
                pbar.update(asynchrounous_calls_at_a_time)
            
            if not scrape_protection_detected:
                remaining_ids = usedIds[(x - 1) * asynchrounous_calls_at_a_time:]
                if remaining_ids:
                    games += asyncio.run(collect_data_from_videoIds(remaining_ids, videoIds_dict, playlistIds_dict, cancel=cancel))

                    pbar.update(len(remaining_ids))


    games.reverse()

    games_file = "data/games.json"
    if scrape_protection_detected:
        games_file = "games_emergency.json"

    

    with open(games_file, "r", encoding="utf-8") as json_file:
        games_dict = json.load(json_file)

        for game_dict in games:
            if game_dict["video_id"] not in games_dict:
                skipped_keys = ["int_views", "upload_d", "game_id"]
                updated_game_dict = {key: value for key, value in game_dict.items() if key not in skipped_keys}
                games_dict[game_dict["video_id"]] = updated_game_dict
    
    with open(games_file, "w", encoding="utf-8") as json_file:
        json.dump(games_dict, json_file, indent=3, ensure_ascii=False)
        
    measurement_file = "data/measurement.json"
    with open(measurement_file, "r", encoding="utf-8") as json_file:
        measurement_dict = json.load(json_file)

    date_now = datetime.now().strftime("%d.%m.%Y")
    if date_now not in measurement_dict:
        measurement_dict[date_now] = dict()
    
    new_measurement = dict()
    for game_dict in games:
        new_measurement[game_dict["video_id"]] =   {"upload_d": game_dict["upload_d"],
                                                    "int_views": game_dict["int_views"]}
    
    measurement_dict[date_now].update(new_measurement)

    with open(measurement_file, "w", encoding="utf-8") as json_file:
        json.dump(measurement_dict, json_file, indent=3, ensure_ascii=False)
    
    


def find_scores():
    params = {"bl1": ["2021", "2022", "2023", "2024", "2025"],
     "bl2": ["2021", "2022", "2023", "2024", "2025"],
     "dfb": ["2023", "2024", "2025"]}
    for comp, yr_list in params.items():
        for yr in yr_list:
            api_call = requests.get(f"https://api.openligadb.de/getmatchdata/{comp}/{yr}")
            api_call.encoding = "utf-8"
            scores_dict = api_call.json()

            competition_translate = {"bl1": "Bundesliga",
                                    "bl2": "2. Bundesliga",
                                    "dfb": "DFB-Pokal"}

            vid_scores = dict()
            with open("data/games.json", "r", encoding="utf-8") as json_file:
                games_dict = json.load(json_file)
                synonyms = get_synonyms()

                for score_dict in scores_dict:
                    home_team = score_dict["team1"]["teamName"]
                    away_team = score_dict["team2"]["teamName"]

                    actual_home_team = get_synonym(home_team, synonyms)
                    home_team = actual_home_team if actual_home_team else home_team

                    actual_away_team = get_synonym(away_team, synonyms)
                    away_team = actual_away_team if actual_away_team else away_team

                    competition_short = score_dict["leagueShortcut"]
                    competition = competition_translate[competition_short]

                    season_int = score_dict["leagueSeason"]
                    season = str(season_int) + "/" + str((season_int % 100) + 1)

                    score1 = None
                    score2 = None
                    for result in score_dict["matchResults"]:
                        if result["resultName"] == "Endergebnis":
                            score1 = result["pointsTeam1"]
                            score2 = result["pointsTeam2"]
                            break

                    for video_id, game_dict in games_dict.items():
                        home_team_g = game_dict["home_team"]
                        away_team_g = game_dict["away_team"]
                        competition_g = game_dict["competition"]
                        season_g = game_dict["season"]
                        if home_team_g == home_team and away_team_g == away_team and competition_g == competition and season_g == season:
                            match_video_id = video_id
                            vid_scores[match_video_id] = dict()
                            vid_scores[match_video_id]["score1"] = score1
                            vid_scores[match_video_id]["score2"] = score2
                            break
                    else:
                        print(f"Game not Found: {home_team} {away_team} {competition} {season}")
            
            with open("data/scores.json", "r", encoding="utf-8") as json_file:
                scores_dict = json.load(json_file)
            with open("data/scores.json", "w", encoding="utf-8") as f:
                json.dump(scores_dict | vid_scores, f, indent=3, ensure_ascii=False)


def display_missing_scores():
    with open("data/games.json", "r", encoding="utf-8") as games_file, open("data/scores.json", "r", encoding="utf-8") as scores_file, open("no_scores.json", "w", encoding="utf-8") as f, open("scores_append.json", "w", encoding="utf-8") as f_append:
        games_dict = json.load(games_file)
        scores_dict = json.load(scores_file)

        missing_videos = []
        scores_append = dict()
        for v_id, game_dict in games_dict.items():
            if v_id not in scores_dict:
                missing_videos.append(game_dict)
                scores_append[v_id] = {"score1": None,
                                        "score2": None}
        
        json.dump(missing_videos, f, indent=3, ensure_ascii=False)
        json.dump(scores_append, f_append, indent=3, ensure_ascii=False)

def append_scores():
    with open("data/scores.json", "r", encoding="utf-8") as scores_file, open("scores_append.json", "r", encoding="utf-8") as scores_append:
        scores_append_dict = json.load(scores_append)
        scores_dict = json.load(scores_file)
    with open("data/scores.json", "w", encoding="utf-8") as scores_file_w:
        json.dump(scores_dict | scores_append_dict, scores_file_w, indent=3, ensure_ascii=False)

CREATE_PLAYLIST_VIDEO_IDS = False
CREATE_GAMES_JSON = True
FIND_SCORES_AND_DATES = False
TESTING = False


def main():
    if CREATE_PLAYLIST_VIDEO_IDS:
        update_jsonfiles()
    if CREATE_GAMES_JSON:
        create_games_json_file(cancel=False)
    if FIND_SCORES_AND_DATES:
        find_scores()
    if TESTING:
        pass
        

if __name__ == "__main__":
    main()

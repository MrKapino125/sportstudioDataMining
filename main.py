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

    #connector=aiohttp.TCPConnector(limit=200)
    async with aiohttp.ClientSession() as session:
        tasks = get_game_tasks(session, videoIds)
        responses = await asyncio.gather(*tasks)
        with tqdm(total=len(responses), desc="Processing Videos", leave=False) as probar:
            for response in responses:
                snippet = await response.text()
                if scrape_protection_detected:
                    continue

                url = str(response.request_info.url)

                videoIdIdx = url.find("watch?v=") + len("watch?v=")
                videoId = url[videoIdIdx:videoIdIdx+11]
                playlistId = videoIds_dict[videoId]
                playlist_number = playlistIds_dict[playlistId]["playlist_number"]
                index = playlistIds_dict[playlistId]["index"]

                league, season = get_league_season(playlist_number, index)
                try:
                    game = collect_scrape_protection(snippet, league, season, playlistId)
                    game["video_id"] = videoId
                except Exception as e:
                    if cancel:
                        scrape_protection_detected = True
                    print(f"Timeout, skipping video {videoId}")
                    with open("skipped/snippet.txt", "w", encoding="utf-8") as json_file:
                        json.dump(snippet, json_file, indent=2)
                games.append(game)
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

def collect_data_game(snippet, league, season, playlist_id=None):
    global once
    snippet = snippet[snippet.find("""videoDetails":""") + len("""videoDetails":"""):]
    
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
    if not once:
        with open("test.json", "w", encoding="utf-8") as json_file:
            json.dump(videoDetails, json_file, indent=2)
        once = True

    game = dict()
    game["videoId"] = videoDetails.get("videoId")
    if game["videoId"] is None:
        raise Exception("Scrape Protection Detected!")

    game["title"] = videoDetails.get("title")
    if game["title"] is None:
        raise Exception("Scrape Protection Detected!")

    home_team, away_team = get_home_away_team(game["title"])
    game["home_team"] = home_team
    game["away_team"] = away_team

    game["int_seconds"] = videoDetails.get("lengthSeconds")
    if game["int_seconds"] is not None: game["int_seconds"] = int(game["int_seconds"])
    #if game["int_seconds"] is None: print("int_seconds: " + game["video_id"])

    game["keywords"] = videoDetails.get("keywords")
    #if game["keywords"] is None: print("keywords: " + game["video_id"])

    game["description"] = videoDetails.get("shortDescription")
    #if game["description"] is None: print("description: " + game["video_id"])

    #game["thumbnail"] = videoDetails["thumbnail"]["thumbnails"]
    #if game["thumbnail"] is None: print(game["video_id"])

    #idx = find_index_helper(videoDetails["subtitle"]["runs"])
    #game["int_views"] = int(snippet["subtitle"]["runs"][idx]["text"].split()[0].replace('.', ''))
    game["int_views"] = videoDetails.get("viewCount")
    if game["int_views"] is not None: game["int_views"] = int(game["int_views"])
    #if game["int_views"] is None: print("int_views: " + game["video_id"])

    game["competition"] = league
    game["season"] = season
    game["playlist_id"] = playlist_id

    return game

def find_index_helper(l):
    for index, e in enumerate(l):
        if 'Aufrufe' in e.get('text', ''):
            return index
    return -1

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
        print(team1)  # print debug
        print(title)
    for team in synonyms:
        synonym = synonyms[team]
        if team2 in synonym:
            away_team = team
            break
    else:
        print(team2)  # print debug
        print(title)

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
            league = "DFB-Pokal"
            match idx:
                case 0:
                    season = "2022/23"
                case 1:
                    season = "2023/24"
                case 2:
                    season = "2024/25"
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
        case 6:
            league = "Bundesliga"
            season = "2024/25"
    return league, season


# MAIN FUNCTIONS
def create_sql():
    sql_string = """INSERT INTO all_data (title, home_team, away_team, int_views, int_seconds, competition, season, video_id) VALUES """

    with open("games.json", "r", encoding="utf-8") as json_file:
        games_dict = json.load(json_file)
        for key, game in games_dict.items():
            title = game["title"]
            home = game["home_team"]
            away = game["away_team"]
            views = game["int_views"]
            seconds = game["int_seconds"]
            competition = game["competition"]
            season = game["season"]
            video_id = game["video_id"]

            sql_string += f"""("{title}", "{home}", "{away}", {views}, {seconds}, "{competition}", "{season}", "{video_id}"),"""

    sql_string = sql_string[:-1]
    sql_string += ";"

    sql_string = sql_string.replace('#', '\\#')

    with open("sql_string.txt", "w", encoding="utf-8") as sqlFile:
        sqlFile.write(sql_string)


def update_jsonfiles(playlists=None):
    playlist_dict = dict()
    videoIds_dict = dict()
    for playlist_number in range(7):
        print(f"Playlist Group {playlist_number + 1}/7")
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
            playlist_dict[mock_playlist_id]["index"] = idx
            playlist_dict[mock_playlist_id]["videoIds"].append(videoId)

    videoIds_json = json.dumps(videoIds_dict, indent=3)
    with open("jsonfiles/videoId_to_playlistId.json", "w") as json_file:
        json_file.write(videoIds_json)

    playlist_ids_json = json.dumps(playlist_dict, indent=3)
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

    games_file = "games.json"
    if scrape_protection_detected:
        games_file = "games_emergency.json"

    with open(games_file, "r", encoding="utf-8") as json_file:
        games_dict = json.load(json_file)
        date_now = datetime.now().strftime("%d.%m.%Y")
        if date_now in games_dict:
            for idx, game_dict in enumerate(games):
                v_id = game_dict["video_id"] 
                if v_id in games_dict[date_now]:
                    games_dict[date_now][v_id]["int_views"] = game_dict["int_views"]
                else:
                    games_dict[date_now][v_id] = game_dict
        else:
            games_dict[date_now] = dict()
            for idx, game_dict in enumerate(games):
                games_dict[date_now][game_dict["video_id"]] = game_dict

    
    with open(games_file, "w", encoding="utf-8") as json_file:
        json.dump(games_dict, json_file, indent=3)


def find_scores_and_dates(video_ids=None):
    games = []
    not_games = []
    with open("games.json", "r", encoding="utf-8") as json_file:
        games_dict = json.load(json_file)
        if video_ids is not None:
            for key, game in games_dict.items():
                if game["videoId"] in video_ids:
                    games.append(game)
                else:
                    not_games.append(game)
        else:
            games = games_dict.values()

        for game in games:
            score = get_score(game)

            game["home_score"] = score[0]
            game["away_score"] = score[1]

    with open("games_old.json", "w", encoding="utf-8") as json_file:
        json_file.write(json.dumps(games_dict, indent=3))


def get_score(game):
    return 1, 0


CREATE_SQL = False
CREATE_PLAYLIST_VIDEO_IDS = False
CREATE_GAMES_JSON = True
FIND_SCORES_AND_DATES = False
TESTING = False


def main():
    if CREATE_SQL:
        create_sql()
    if CREATE_PLAYLIST_VIDEO_IDS:
        update_jsonfiles()
    if CREATE_GAMES_JSON:
        create_games_json_file(cancel=False)
    if FIND_SCORES_AND_DATES:
        find_scores_and_dates()
    if TESTING:
        with open("games.json", "r", encoding="utf-8") as json_file:
            games_dict = json.load(json_file)
            get_score(games_dict["game0"])

        api_call = requests.get("https://api.openligadb.de/getmatchdata/bl1/2022/8")
        games_dict = api_call.json()
        print(games_dict)


if __name__ == "__main__":
    main()

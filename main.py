import requests
import helper
import pdo
import json
import ast


def get_urls_from_txt(idx=None):
    urls = []
    match idx:
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
        case _:
            with open("playlist_urls.txt", "r") as f:
                file = f.readlines()
                for line in file:
                    urls.append(line.strip())
    return urls


def collect_data_game(videoId, league, season):
    q = "https://www.youtube.com/watch?v=" + videoId
    response = requests.get(q)
    snippet = response.text

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

    game = dict()
    game["video_id"] = videoDetails["videoId"]
    game["title"] = videoDetails["title"]
    game["int_seconds"] = int(videoDetails["lengthSeconds"])
    game["keywords"] = videoDetails["keywords"]
    game["description"] = videoDetails["shortDescription"]
    #game["thumbnail"] = videoDetails["thumbnail"]["thumbnails"]
    game["int_views"] = int(videoDetails["viewCount"])
    game["competition"] = league
    game["season"] = season

    return game


def collect_data_playlist(playlistId, length, avoid, league, season):
    games = []

    q = "https://www.youtube.com/playlist?list=" + playlistId
    response = requests.get(q)
    snippet = response.text

    for idx in range(length):
        print(f"Game {idx+1}/{length}")

        videoIdx = idx+1
        if videoIdx in avoid:
            snippet = snippet[snippet.find("""thumbnail":{"thumbnails":[{"url"""):]
            snippet = snippet[snippet.find("""{"label":"""):]
            continue

        snippet = snippet[snippet.find("videoId") + len("videoId") + 3:]
        videoId = snippet[:11]

        game = collect_data_game(videoId, league, season)
        games.append(game)

        snippet = snippet[snippet.find("""thumbnail":{"thumbnails":[{"url"""):]
        snippet = snippet[snippet.find("""{"label":"""):]

    return games


def get_synonyms():
    synonyms = dict()

    with open("synonyms.txt", "r") as f:
        file = f.readlines()
        synonyms_lines = []
        for line in file:
            synonyms_lines.append(line.strip())
        for line in synonyms_lines:
            club = line[:line.find(":")]
            line = line[line.find(":") + 1:]
            synonyms[club] = line.split(",")

    return synonyms


def create_sql():
    sql_string = """INSERT INTO processed_data (title, home_team, away_team, int_views, int_seconds, competition, season, video_id) VALUES """

    with open("games.json", "r") as json_file:
        games_dict = json.load(json_file)
        for key, game in games_dict.items():
            title = game["title"]
            home = game["home_team"]
            away = game["away_team"]
            views = game["int_views"]
            seconds = game["int_seconds"]
            competition = game["competition"]
            season = game["season"]
            video_id = game["videoId"]

            sql_string += f"""("{title}", "{home}", "{away}", {views}, {seconds}, "{competition}", "{season}", "{video_id}"),"""

    sql_string = sql_string[:-1]
    sql_string += ";"

    with open("sql_string.txt", "w") as sqlFile:
        sqlFile.write(sql_string)


def playlist_to_dict(playlist_string, league, season):
    playlist_id, length, avoid = parse_playlist_string(playlist_string)
    games = collect_data_playlist(playlist_id, length, avoid, league, season)

    games_dict = dict()
    for idx, game in enumerate(games):
        games_dict["game" + str(idx)] = game

    return games_dict


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


def get_league_season(playlist_number, idx):
    league = None
    season = None
    match playlist_number:
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
        case 4:
            league = "DFB-Pokal"
            match idx:
                case 0:
                    season = "2022/23"
                case 1:
                    season = "2023/24"
        case 5:
            league = "Relegation"
            match idx:
                case 0:
                    season = "2021/22"
                case 1:
                    season = "2022/23"
                case 2:
                    season = "2023/24"
    return league, season


get_sql = False
to_json = True

def main():
    if get_sql:
        create_sql()
    if to_json:
        games_dicts = []
        #for playlist_number in range(6):
            #print(f"Playlist Group {playlist_number + 1}/6")

            #urls = get_urls_from_txt(playlist_number)

            #for idx, playlist_string in enumerate(urls):
                #print(f"Playlist {idx + 1}/{len(urls)}")
                #league, season = get_league_season(playlist_number, idx)
                #games_dicts.append(playlist_to_dict(playlist_string, league, season))

        with open("playlists/Supercup_games.txt", "r") as file:
            f = file.readlines()
            lines = []
            for line in f:
                lines.append(line.strip())

            for idx, videoId in enumerate(lines):
                league = "DFL-Supercup"
                season = None
                match idx:
                    case 0:
                        season = "2021/22"
                    case 1:
                        season = "2022/23"
                    case 2:
                        season = "2023/24"
                games_dicts.append(collect_data_game(videoId, league, season))

        games_dict = dict()
        for idx, game_dict in enumerate(games_dicts):
            games_dict["game" + str(idx)] = game_dict

        games_json = json.dumps(games_dict, indent=3)
        with open("games_test.json", "w") as json_file:
            json_file.write(games_json)



if __name__ == "__main__":
    main()

    #games_json = json.dumps(games_dict, indent=3)
    #with open("games_test.json", "w", encoding="utf-8") as json_file:
        #json_file.write(games_json)
    #pdo_connection = pdo.PDO("module=mysql;host=localhost;user=main_acc;passwd=pass;db=sportstudio_datamining")

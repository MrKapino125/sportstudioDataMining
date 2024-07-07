import requests
import helper


def create_urls():
    urls = []
    with open("playlist_urls.txt", "r") as f:
        file = f.readlines()
        for line in file:
            urls.append(line.strip())
    return urls


def collect_data():
    season = dict()

    urls = create_urls()

    for idx, url in enumerate(urls):

        line = url.split(",")
        u = line[0]
        avoid = []
        length = 9
        if len(line) == 2:
            avoid = [int(line[1])]
        elif len(line) > 2:
            length = int(line[-1])
            if line[1] != "":
                for a in line[1:-1]:
                    avoid.append(int(a))

        q = "https://www.youtube.com/playlist?list=" + u
        response = requests.get(q)
        snippet = response.text
        snippet = snippet[snippet.find("""{"label":"""):]

        videos = dict()
        playlist_idx = 1
        lookup_idx = 1
        while playlist_idx < length + 1:
            if lookup_idx in avoid:
                snippet = snippet[snippet.find("""thumbnail":{"thumbnails":[{"url"""):]
                snippet = snippet[snippet.find("""{"label":"""):]
                lookup_idx += 1
                continue

            key = "video" + str(playlist_idx)
            value = {}
            snippet = snippet[10:]
            title_end_idx = snippet.find("von sportstudio fußball") - 1
            value["title"] = snippet[:title_end_idx]

            snippet = snippet[title_end_idx + 2 + len("von sportstudio fußball"):]
            clicks_end_idx = snippet.find("Aufrufe") - 1
            value["clicks"] = snippet[:clicks_end_idx]

            snippet = snippet[snippet.find("""{"label":"""):]
            snippet = snippet[snippet.find("simpleText") + 13:]
            time_end_idx = snippet.find("}") - 1
            value["time"] = snippet[:time_end_idx]

            videos[key] = value

            snippet = snippet[snippet.find("""thumbnail":{"thumbnails":[{"url"""):]
            snippet = snippet[snippet.find("""{"label":"""):]

            playlist_idx += 1
            lookup_idx += 1

        key = "Spieltag" + str(idx + 1)
        season[key] = videos

    return season


def update_raw(season):
    with open("data_raw.txt", "w") as data_file:
        for spieltag in season:
            videos = season[spieltag]
            for video in videos:
                value = videos[video]
                title = value["title"]
                title = title.replace("\u202f", " ")
                value["title"] = title
                data_file.write(value["title"] + "\n")
                data_file.write(value["clicks"] + "\n")
                data_file.write(value["time"] + "\n")


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


def get_season_dict():
    season = dict()

    gamecount = 1
    with open("data_raw.txt", "r") as file:
        f = file.readlines()
        lines = []
        for line in f:
            lines.append(line.strip())

        len_lines = len(lines)//3
        for idx in range(len_lines):
            key = "game" + str(gamecount)
            true_idx = 3*idx
            value = dict()
            value["title"] = lines[true_idx]
            value["clicks"] = lines[true_idx+1]
            value["time"] = lines[true_idx+2]
            season[key] = value
            gamecount += 1

    return season


def parse_data(season, synonyms):
    views = dict()
    times = dict()
    views_opponent = dict()
    for club in synonyms:
        views_opponent[club] = dict()

    for game_key in season:
        game = season[game_key]
        match = game["title"]
        highlight_check = match[:match.find("Highlights")]
        if highlight_check.find("|") == -1:
            match = match[:match.find("Highlights") - 1]
        else:
            match = match[:match.find("|") - 1]
        vs_idx = match.find(" - ")
        if vs_idx == -1:
            vs_idx = match.find(" – ")
        team1 = match[:vs_idx]
        team2 = match[vs_idx + 3:]

        while team1[-1] == " ":
            team1 = team1[:-1]
        while team2[-1] == " ":
            team2 = team2[:-1]

        for team in synonyms:
            synonym = synonyms[team]
            if team1 in synonym:
                team1 = team
                break
        else:
            print(team1)                        #print debug
            print(game["title"])
        for team in synonyms:
            synonym = synonyms[team]
            if team2 in synonym:
                team2 = team
                break
        else:
            print(team2)                        #print debug
            print(game["title"])
        if team1 in views:
            views[team1].append(game["clicks"])
        else:
            views[team1] = [game["clicks"]]
        if team1 in times:
            times[team1].append(game["time"])
        else:
            times[team1] = [game["time"]]
        if team2 in views_opponent[team1]:
            if views_opponent[team1][team2]["Heim"] is None:
                views_opponent[team1][team2]["Heim"] = [game["clicks"]]
            else:
                views_opponent[team1][team2]["Heim"].append(game["clicks"])
        else:
            views_opponent[team1][team2] = {"Heim": [game["clicks"]],
                                            "Gast": None}

        if team2 in views:
            views[team2].append(game["clicks"])
        else:
            views[team2] = [game["clicks"]]
        if team2 in times:
            times[team2].append(game["time"])
        else:
            times[team2] = [game["time"]]
        if team1 in views_opponent[team2]:
            if views_opponent[team2][team1]["Gast"] is None:
                views_opponent[team2][team1]["Gast"] = [game["clicks"]]
            else:
                views_opponent[team2][team1]["Gast"].append(game["clicks"])
        else:
            views_opponent[team2][team1] = {"Heim": None,
                                            "Gast": [game["clicks"]]}

    return views, times, views_opponent


def create_mean_views(views):
    mean_views = dict()

    for club in views:
        clicks = views[club]

        summe = 0
        for click in clicks:
            summe += helper.str_to_int(click)

        mean_views[club] = int(summe / len(clicks))

    return mean_views


def create_mean_times(times):
    mean_times = dict()

    for club in times:
        club_times = times[club]
        for idx, t in enumerate(club_times):
            minutes_seconds = t.split(":")
            seconds = int(minutes_seconds[0]) * 60 + int(minutes_seconds[1])
            club_times[idx] = seconds
        mean = int(sum(club_times) / len(club_times))
        minutes = str(mean // 60)
        seconds = str(mean % 60)
        if len(seconds) == 1:
            seconds = "0" + seconds
        mean_times[club] = minutes + ":" + seconds

    return mean_times


def create_number_of_games(views):
    number_of_games = dict()

    for club in views:
        number_of_games[club] = len(views[club])

    return number_of_games


def update_comprehensive(mean_views, mean_times, number_of_games, views, synonyms):
    mean_views = helper.sort_dict_by_values_and_games(mean_views, number_of_games)

    teams_under_6_games = False

    with open("data_comprehensive.txt", "w") as file:
        for club in mean_views:
            int_views = []
            maximum = max([len(club) for club in synonyms])
            mean = helper.add_dots_to_int(str(mean_views[club]))
            avg_time = mean_times[club]
            for view in views[club]:
                int_views.append(helper.str_to_int(view))
            max_views = helper.add_dots_to_int(max(int_views))
            min_views = helper.add_dots_to_int(min(int_views))
            if not teams_under_6_games and number_of_games[club] < 6:
                file.write("\n")
                file.write("max 5 games:\n")
                teams_under_6_games = True
            file.write(club + (maximum-len(club)+1)*" " + "avg: " + mean + (10-len(mean))*" " + "max: " + max_views + (11-len(max_views))*" " + "min: " + min_views + (10-len(min_views))*" " + "average time: " + avg_time + "  games: " + str(number_of_games[club]) + "\n")


def update_home_away_dict(views_opponent):
    with open("home_away_dict.txt", "w") as file:
        for club, opponent_dict in views_opponent.items():
            file.write(f"{club}:\n")
            for opponent, home_away_dict in opponent_dict.items():
                file.write(f"  {opponent}:\n")
                file.write("    home: ")
                if home_away_dict["Heim"] is not None:
                    file.write(", ".join(home_away_dict["Heim"]))
                file.write("\n")
                file.write("    away: ")
                if home_away_dict["Gast"] is not None:
                    file.write(", ".join(home_away_dict["Gast"]))
                file.write("\n")


collect = False
override = True


def main():
    if collect:
        season = collect_data()
        update_raw(season)
    if override:
        synonyms = get_synonyms()
        season = get_season_dict()
        views, times, views_opponent = parse_data(season, synonyms)
        mean_views = create_mean_views(views)
        mean_times = create_mean_times(times)
        number_of_games = create_number_of_games(views)
        update_comprehensive(mean_views, mean_times, number_of_games, views, synonyms)
        update_home_away_dict(views_opponent)


if __name__ == "__main__":
    main()

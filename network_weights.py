import twitter
from functools import partial
import sys
import time
from urllib.error import URLError
from http.client import BadStatusLine
from tqdm import tqdm
import re
import csv
import json
import os
import networkx
import operator
import matplotlib.pyplot as plt
import pyecharts.options as opts
from pyecharts.charts import Graph


MAXNUM = 10000


# Example 1 in Cookbook: Accessing Twitter's API for development purposes
def oauth_login():
    """
    :return:
        Twitter API
    """

    CONSUMER_KEY = 'IMKNSTaK34HCHXCtZ3CEmm7MZ'
    CONSUMER_SECRET = 'xHPrHX5JlYvkECUVGjA1mGjSA7mKXgagXY3rral2pXJGrd3rsL'
    OAUTH_TOKEN = '865048473988505600-TytCBfh66g6c5tgBmrqRketcc6DT4Lo'
    OAUTH_TOKEN_SECRET = 'RpLH9dtRcCTdYvUot9SscfSxB6J13Wu9mDFRcTavjIWR4'
    auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET)
    twitter_api = twitter.Twitter(auth=auth)
    print(twitter_api)
    return twitter_api


# Example 16 in Cookbook: Making robust Twitter requests
def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):

        if wait_period > 3600:  # Seconds
            print('Too many retries. Quitting.', file=sys.stderr)
            raise e

        # See https://developer.twitter.com/en/docs/basics/response-codes
        # for common codes

        if e.e.code == 401:
            print('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            print('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429:
            print('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                print("Retrying in 15 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60 * 15 + 5)
                print('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e  # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print('Encountered {0} Error. Retrying in {1} seconds'.format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function

    wait_period = 2
    error_count = 0

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise


# Example 21. Harvesting a user's tweets in Cookbook
def harvest_user_timeline(twitter_api, screen_name=None, user_id=None, max_results=MAXNUM):
    assert (screen_name is not None) != (user_id is not None), \
        "Must have screen_name or user_id, but not both"

    kw = {  # Keyword args for the Twitter API call
        'count': 200,
        'trim_user': 'true',
        'include_rts': 'true',
        'since_id': 1
    }

    if screen_name:
        kw['screen_name'] = screen_name
    else:
        kw['user_id'] = user_id

    results = []

    tweets = make_twitter_request(twitter_api.statuses.user_timeline, **kw)

    if tweets is None:  # 401 (Not Authorized) - Need to bail out on loop entry
        selected_tweets = []
        month = ""
        print("No tweet was fetched")
    else:
        month = tweets[0]["created_at"].split()[1]
        if month in ['Jan', 'Feb']:
            print('Fetched {0} tweets of {1}. Month {2}'.format(len(tweets), (screen_name or user_id), month),
                  file=sys.stderr)
        selected_tweets = [tweet for tweet in tweets if tweet["created_at"].split()[-1] == "2020"
                           and tweet["created_at"].split()[1] in ['Jan', 'Feb']]
    results += selected_tweets
    if month in ['Jan', 'Feb']:
        print('Selected {0} tweets of {1}.'.format(len(selected_tweets), (screen_name or user_id)),
              file=sys.stderr)

    page_num = 1

    while tweets is not None and len(tweets) > 0 and len(results) < max_results and month != "Dec":
        # Necessary for traversing the timeline in Twitter's v1.1 API:
        # get the next query's max-id parameter to pass in.
        # See https://dev.twitter.com/docs/working-with-timelines.
        kw['max_id'] = min([tweet['id'] for tweet in tweets]) - 1

        tweets = make_twitter_request(twitter_api.statuses.user_timeline, **kw)
        if not tweets:
            break
        month = tweets[0]["created_at"].split()[1]
        """
        if month in ['Jan', 'Feb'] and len(tweets) > 0:
            print('Fetched {0} tweets of {1}. Month {2}'.format(len(tweets), (screen_name or user_id), month),
                  file=sys.stderr)
        """
        selected_tweets = [tweet for tweet in tweets if tweet["created_at"].split()[-1] == "2020"
                           and tweet["created_at"].split()[1] in ['Jan', 'Feb']]
        results += selected_tweets
        if month in ['Jan', 'Feb'] and len(selected_tweets) > 0:
            print('Selected {0} tweets of {1}.'.format(len(selected_tweets), (screen_name or user_id)),
                  file=sys.stderr)

        page_num += 1

    print('Done fetching tweets of {0}'.format((screen_name or user_id)), file=sys.stderr)

    results = results[:max_results]

    save_json("./tweets/{0}".format((screen_name or user_id)), results)


# Example 17 in Cookbook: Resolving user profile information (from Cookbook)
def get_user_profile(twitter_api, screen_names=None, user_ids=None):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None), "Must have screen_names or user_ids, but not both"

    items_to_info = {}

    items = screen_names or user_ids

    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See http://bit.ly/2Gcjfzr for details.

        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup,
                                            screen_name=items_str)
        else:  # user_ids
            response = make_twitter_request(twitter_api.users.lookup,
                                            user_id=items_str)

        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else:  # user_ids
                items_to_info[user_info['id']] = user_info

    return items_to_info


def get_rt_attributions(twitter_api, tweet, screen_name):
    # Regex adapted from Stack Overflow (http://bit.ly/1821y0J)
    rt_patterns = re.compile(r"(RT|via)((?:\b\W*@\w+)+)", re.IGNORECASE)
    rt_attributions = []

    # Inspect the tweet to see if it was produced with /statuses/retweet/:id.
    # See https://dev.twitter.com/docs/api/1.1/get/statuses/retweets/%3Aid.

    if 'retweeted_status' in tweet:
        attribution = None
        if 'screen_name' in tweet['retweeted_status']['user']:
            attribution = tweet['retweeted_status']['user']['screen_name']
        elif 'id' in tweet['retweeted_status']['user']:
            user_id = tweet['retweeted_status']['user']['id']
            profile = get_user_profile(twitter_api, user_ids=[user_id])
            attribution = profile[user_id]['screen_name']
        if attribution is not None:
            rt_attributions.append(attribution)

    # Also, inspect the tweet for the presence of "legacy" retweet patterns
    # such as "RT" and "via", which are still widely used for various reasons
    # and potentially very useful. See https://dev.twitter.com/discussions/2847
    # and https://dev.twitter.com/discussions/1748 for some details on how/why.

    try:
        rt_attributions += [
            mention.strip()
            for mention in rt_patterns.findall(tweet['text'])[0][1].split()
        ]
    except IndexError as e:
        pass

    # Filter out any duplicates
    sources = list(set([rta.strip("@").lower() for rta in rt_attributions]))
    if sources:
        print("\nGot the RT attributions of tweet {0}. {1}".format(tweet["id"], sources))

    return [(source, screen_name) for source in sources if source != screen_name]


def select_nba_tweets(screen_name=None, user_id=None, tweet=None):
    assert (screen_name is not None) != (user_id is not None), "Must have screen_name or user_id, but not both"
    assert tweet is not None
    # time
    time_str = tweet["created_at"].split()
    # must between 02/09/20 and 02/23/20
    if time_str[-1] != "2020" or time_str[1] not in ["Jan", "Feb"]:
        return False
    """
    # user mentions
    user_mentions = [user_mention['screen_name'] for user_mention in tweet['entities']['user_mentions']]
    roster_twitters = read_list("roster_twitters.csv")
    # if mentioned the member of the name list or the roster, return true
    if list(set(name_list).intersection(set(user_mentions))) or \
       list(set(roster_twitters).intersection(set(user_mentions))):
        return True
    """
    # hashtag
    hashtags = [hashtag['text'].lower() for hashtag in tweet['entities']['hashtags']]
    # if included any of the hashtags in the list, return true
    hashtag_intersection = list(set(hashtags).intersection(popular_hashtags))
    if hashtag_intersection:
        for hashtag in hashtag_intersection:
            if hashtag in hashtag_freq:
                hashtag_freq[hashtag] += 1
            else:
                hashtag_freq[hashtag] = 1
        return True
    """
    # keyword
    text = tweet["text"].lower()
    """
    # otherwise, return false
    return False


def read_list(file_name):
    with open(file_name, 'r') as f:
        if "csv" in file_name.split("."):
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    break
        elif "txt" in file_name.split("."):
            row = f.readline().split(" #")
        f.close()
    return row


def save_json(filename, data):
    print("Saving data to json...", file=sys.stderr)
    with open('{0}.json'.format(filename), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def load_json(filename):
    print("Loading data from json...", file=sys.stderr)
    with open('{0}.json'.format(filename), 'r', encoding='utf-8') as f:
        return json.load(f)


def add_nodes(graph, _edges):
    if _edges:
        # get nodes
        _s = str([list(edge) for edge in _edges])
        _s = _s.replace('[', '')
        _s = _s.replace(']', '')
        _nodes = list(set(list(eval(_s))))
        graph.add_nodes_from(_nodes)
        graph.add_edges_from(_edges)
        print("Got nodes: {0}".format(len(_nodes)))
        print("Got edges: {0}".format(len(_edges)))


def draw_graph(data_, title):
    nodes_ = [
        {
            "name": node_["label"],
            "symbol": "circle",
            "symbolSize": int(node_["weight"] / 10) + 5,
            "value": node_["weight"],
            # "itemStyle": {"normal": {"color": node["color"]}},
        }
        for node_ in data_["nodes"]
    ]

    edges_ = [
        {"source": edge[0], "target": edge[1],
         "value": lower_edge_weight["({0}, {1})".format(edge[0], edge[1])],
         "symbol": [None, "arrow"], "symbol_size": [0, 1]}
        for edge in data_["edges"]
    ]

    (
        Graph(init_opts=opts.InitOpts(width="1600px", height="800px"))
        .add(
            series_name="",
            nodes=nodes_,
            links=edges_,
            is_roam=True,
            is_focusnode=True,
            layout="force",
            is_selected=False,
            is_draggable=False,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=0.5, curve=0.3, opacity=0.7),

        )
        .set_global_opts(title_opts=opts.TitleOpts(title=title))
        .render("./graphs/{0}.html".format(title))
    )


if __name__ == "__main__":
    Twitter_API = oauth_login()
    name_list = sorted(read_list("nba_news_ids.csv"))
    # lower_name_list = [name.lower() for name in name_list]
    print(name_list)
    popular_hashtags = set(read_list("popular_nba_basketball_hashtags.txt"))
    print(popular_hashtags)
    edge_weight = {}
    node_weight = {}
    node_edge = {}
    hashtag_freq = {}
    """
        Step 1: harvest the tweet timeline of each account
    """
    """
    if not os.path.exists("./tweets"):
        os.makedirs("./tweets")
    start_time = time.time()
    last_time = start_time
    current_time = start_time
    for i in tqdm(range(len(name_list))):
        print("\nHarvest tweet timeline of %s..." % name_list[i], file=sys.stderr)
        harvest_user_timeline(Twitter_API, name_list[i])
        current_time = time.time()
        print("\nTotal Time: %.4f s. Last iteration time: %.4f s." %
              ((current_time - start_time), (current_time - last_time)), file=sys.stderr)
        last_time = current_time
    """
    """
        Step 2: select tweets about 2020 NBA All-Star Game and update weights
    """
    """
    for i in tqdm(range(len(name_list))):
        # print("Selecting NBA news tweets of %s..." % name_list[i], file=sys.stderr)
        user_tweets = load_json("./tweets/{0}".format(name_list[i]))
        num_news_tweets = 0
        for j in tqdm(range(len(user_tweets))):
            if select_nba_tweets(name_list[i], tweet=user_tweets[j]):
                num_news_tweets += 1
                if name_list[i] in node_weight:
                    node_weight[name_list[i]] += 1
                else:
                    node_weight[name_list[i]] = 1
                # edge = (source, retweet)
                edges = get_rt_attributions(Twitter_API, user_tweets[j], name_list[i])
                for edge in edges:
                    for node in edge:
                        if node in node_edge:
                            node_edge[node] += 1
                        else:
                            node_edge[node] = 1
                    edge_str = "({0}, {1})".format(edge[0], edge[1])
                    if edge_str in edge_weight:
                        edge_weight[edge_str] += 1
                    else:
                        edge_weight[edge_str] = 1
        print("\n%d NBA news tweets were found" % num_news_tweets)
        save_json("edge_weight", edge_weight)
        save_json("node_weight", node_weight)
        save_json("node_edge", node_edge)
        save_json("hashtag_freq", hashtag_freq)
    """
    """
        Step 3: draw a directional graph of the edges and weights
    """
    network = networkx.DiGraph()
    if not edge_weight:
        edge_weight = load_json("edge_weight")
    lower_edge_weight = {edge_str.lower(): 0 for edge_str in edge_weight}
    for edge_str in edge_weight:
        lower_edge_weight[edge_str.lower()] += edge_weight[edge_str]

    if not node_weight:
        node_weight = load_json("node_weight")
    lower_node_weight = {node.lower(): 0 for node in node_weight}
    for node in node_weight:
        lower_node_weight[node.lower()] += node_weight[node]

    edges = [tuple(edge_str[1:-1].split(", ")) for edge_str in lower_edge_weight]
    add_nodes(network, edges)
    networkx.draw_networkx(network)
    data = {}
    s = str([list(edge) for edge in edges])
    s = s.replace('[', '')
    s = s.replace(']', '')
    nodes = list(set(list(eval(s))))
    for node in nodes:
        if node not in lower_node_weight:
            lower_node_weight[node] = list(eval(s)).count(node)
    data["nodes"] = [{"label": node, "weight": lower_node_weight[node], "color": ""} for node in nodes]
    data["edges"] = edges
    draw_graph(data, "NBA News Social Network")





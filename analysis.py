from network_weights import *
from network_nodes_edges import *
from pyecharts.charts import Bar
import pyecharts.options as opts


def print_distribution(distribution, title, xlabel, ylabel, sortByX=False, sortByY=False):
    """
    :param distribution: dict of (item, freq)
    :return:
    """
    assert not (sortByX and sortByY)

    x_vals = list(distribution.keys())
    y_vals = list(distribution.values())

    if sortByX:
        x_vals.sort()
        y_vals = [distribution[val] for val in x_vals]
    if sortByY:
        x_vals = sorted(x_vals, key=lambda x: distribution[x], reverse=True)
        y_vals = [distribution[val] for val in x_vals]

    x_vals = [str(val) for val in x_vals]
    y_vals = [str(val) for val in y_vals]

    bar = (
        Bar()
        .add_xaxis(x_vals)
        .add_yaxis('frequency', y_vals)
        .set_global_opts(title_opts=opts.TitleOpts(title=title),
                         xaxis_opts=opts.AxisOpts(name=xlabel),
                         yaxis_opts=opts.AxisOpts(name=ylabel))
    )
    bar.render('./graphs/{0}.html'.format(title))


def statistic_analysis():
    # total tweets fetched
    total_tweets_fetched = 0
    user_list = sorted(read_list("nba_news_ids.csv"))
    for user in user_list:
        fetched_tweets = load_json("./tweets/{0}".format(user))
        total_tweets_fetched += len(fetched_tweets)
    print("Total tweets fetched: %d" % total_tweets_fetched)
    # total NBA news tweets selected
    node_weights = load_json("node_weight")
    lower_node_weights = {node.lower(): 0 for node in node_weights}
    for node in node_weights:
        lower_node_weights[node.lower()] += node_weights[node]
    total_nba_news_tweets = sum(list(lower_node_weights.values()))
    print("Total NBA news tweets selected: %d" % total_nba_news_tweets)
    # node weights distribution
    node_weight_freq = {}
    for value in lower_node_weights.values():
        if value in node_weight_freq:
            node_weight_freq[value] += 1
        else:
            node_weight_freq[value] = 1
    print_distribution(node_weight_freq, "Node Weight Distribution", "Weights",
                       "Frequency", sortByX=True)
    # retweet edge count
    edge_count = load_json("node_edge")
    lower_edge_count = {node.lower(): 0 for node in edge_count}
    for node in edge_count:
        lower_edge_count[node.lower()] += edge_count[node]
    print_distribution(lower_edge_count, "Number of the Retweet Edges",
                       "Node", "Number of the Retweet Edge", sortByY=True)
    # frequency of hashtag use distribution
    hashtag_use_freq = load_json("hashtag_freq")
    print_distribution(hashtag_use_freq, "Frequency of Hashtag Use Distribution",
                       "Hashtag", "Frequency of Use", sortByY=True)


if __name__ == "__main__":
    if not os.path.exists("./graphs"):
        os.makedirs("./graphs")
    statistic_analysis()

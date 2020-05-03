import twitter
from functools import partial
import sys
import time
from urllib.error import URLError
from http.client import BadStatusLine
import operator
import csv


MAXNUM = 1000


# Example 1 in Cookbook: Accessing Twitter's API for development purposes
def oauth_login():
    """
    :return:
        Twitter API
    """

    # fill in the oauth keys and secrets of yours
    CONSUMER_KEY = ''
    CONSUMER_SECRET = ''
    OAUTH_TOKEN = ''
    OAUTH_TOKEN_SECRET = ''
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


# search for NBA news IDs
def search_nba_news_ids(twitter_api, k="NBA news", limit=MAXNUM):
    print('Fetching NBA news IDs of "%s" (limit %d IDs)...' % (k, limit))
    if limit == 0:
        return None

    search_ids = partial(make_twitter_request, twitter_api.users.search, count=20, include_entities=False)

    results = []

    p = 1
    last_respond = []
    while len(results) < limit:
        respond = search_ids(q=k, page=p)
        if respond is not None and respond != last_respond:
            results += respond
            last_respond = respond
        else:
            break
        p += 1

    print("Totally fetched %d results" % len(results))

    # select popular and verified accounts from the result
    nba_news_accounts = [user for user in results if user["verified"] and user["followers_count"] >= 10000]

    print("Selected %d IDs from %d results" % (len(nba_news_accounts), len(results)))

    sorted_accounts = sorted(nba_news_accounts,
                             key=operator.itemgetter('followers_count'),
                             reverse=True)

    ids = [account["id"] for account in sorted_accounts]
    screen_name = [account["screen_name"] for account in sorted_accounts]

    # return the IDs of the most popular NBA news accounts of the limit number
    return ids[:limit], screen_name[:limit]


def save_list(name_list, file_name="nba_news_ids.csv"):
    with open(file_name, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(name_list)
        f.close()


if __name__ == "__main__":
    Twitter_API = oauth_login()
    keywords = ["NBA news", "NBA", "Sports News", "men's basketball"]
    nba_news_ids = []
    nba_news_names = []
    for keyword in keywords:
        ids, names = search_nba_news_ids(Twitter_API, k=keyword)
        if ids is not None and names is not None:
            nba_news_ids += ids
            nba_news_names += names
            print(names)
    nba_news_names = list(set(nba_news_names))
    print(nba_news_names)
    print(len(nba_news_names))
    save_list(nba_news_names, "nba_news_ids.csv")


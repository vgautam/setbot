import logging
import operator
import os
import random
import re
from datetime import datetime

import flask
import pytz
from slack_sdk import WebClient
from slackeventsapi import SlackEventAdapter

app = flask.Flask(__name__)
slack_signing_secret = os.environ["SLACK_SIGNING_SECRET"]
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)
client = WebClient(os.environ.get('SLACK_BOT_TOKEN'))

logger = logging.getLogger('setbot')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('setbot.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

pacific = pytz.timezone('US/Pacific')
set_score_regex = re.compile(r'(?:(?P<h>\d) hours )?'
                             r'(?:(?P<m>\d\d) minutes and )?'
                             r'(?P<s>\d\d\.\d\d\d) seconds')
USER_TIMES = {}
CURR_DATE = datetime.now(pacific).date()

compliments = [':tada: Nice job',
               ":knife: You're killing it",
               ':heart: Impressive',
               ":zap: You're a sub-minute superstar",
               ":trophy: Keep this up and you'll be champion soon",
               ":star-struck: You're a force to be reckoned with",
               ':four_leaf_clover: I hope the rest of your day goes as well as your daily set did',
               ":coffee: I see you're putting that coffee to good use"]


def parse_score(match):
    hours = int(match.group('h')) if match.group('h') else 0
    mins = int(match.group('m')) if match.group('m') else 0
    secs = float(match.group('s'))
    time_in_seconds = float(hours*60*60) + float(mins * 60) + secs
    logger.info('Parsed the time in seconds')
    return time_in_seconds


def create_leaderboard(times):
    logger.debug(f'Times are: {times}')
    sorted_times = sorted(times.items(), key=operator.itemgetter(1))
    logger.debug(f'Sorted times are: {sorted_times}')
    text = 'LEADERBOARD :trophy:\n'
    ordinal_mapping = {1: 'first', 2: 'second', 3: 'third'}
    for i in range(1,4):
        if len(sorted_times) >= i:
            item = sorted_times[i-1]
            user = item[0]
            time = item[1]
            text += f':{ordinal_mapping[i]}_place_medal:: <@{user}> ({time}s)\n'
    return text


def post_leaderboard(event: dict):
    leaderboard = create_leaderboard(USER_TIMES)
    channel_id = event['channel']
    client.chat_postMessage(
        channel=channel_id,
        text=leaderboard
    )
    logger.info('Posted leaderboard')


# pylint: disable=global-statement
def update_date():
    global CURR_DATE, USER_TIMES
    if CURR_DATE != datetime.now(pacific).date():
        CURR_DATE = datetime.now(pacific).date()
        USER_TIMES = {}
        logger.info("New day - cleared leaderboard")


# pylint: disable=global-statement
def add_to_scores(time_in_seconds, event):
    global USER_TIMES
    user = event['user']
    USER_TIMES[user] = time_in_seconds
    logger.info('Added score to list of scores')


def sub_minute_reaction(event: dict):
    channel_id = event['channel']
    thread_ts = event['ts']
    user = event['user']

    client.reactions_add(
        channel=channel_id,
        name='fire',
        timestamp=thread_ts
    )
    logger.info('Added a fire emoji reaction')
    compliment = random.choice(compliments)
    client.chat_postMessage(
        channel=channel_id,
        text=f'{compliment}, <@{user}>!',
        thread_ts=thread_ts
    )
    logger.info('Replied with a compliment')


def match_score(text):
    return set_score_regex.search(text)


@slack_events_adapter.on('message')
def handle_message(event_data: dict):
    event = event_data['event']
    logger.debug('Handling a message')
    if 'subtype' in event:
        return
    update_date()
    text = event['text'].lower()
    match = match_score(text)
    if match:
        logger.debug(f'Found a set score in the message ({match.group(0)})')
        time_in_seconds = parse_score(match)
        add_to_scores(time_in_seconds, event)
        if time_in_seconds < 60:
            sub_minute_reaction(event)
    if 'leaderboard' in text:
        post_leaderboard(event)
    logger.debug('Handled the message')


@slack_events_adapter.on('error')
def error_handler(err):
    print("ERROR: " + str(err))
    logger.error(str(err))


@app.route("/")
def hello():
    return "Hello, World! (aka Greetings, Vasundhara!)"

if __name__ == '__main__':
    app.run(debug=True)

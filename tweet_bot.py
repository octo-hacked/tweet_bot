import os
import time
import schedule
import tweepy
import logging
from flask import Flask
from threading import Thread
from datetime import datetime

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Flask Uptime Server ---
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Tweet bot is running on Render!"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# --- Load tweets from tweet.txt ---
def load_tweets():
    try:
        with open("tweet.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"❌ Failed to load tweets: {e}")
        return []

# --- Track tweet index ---
def get_tweet_index():
    try:
        if os.path.exists("last_index.txt"):
            with open("last_index.txt", "r") as f:
                return int(f.read().strip())
        return 0
    except:
        return 0

def save_tweet_index(index):
    try:
        with open("last_index.txt", "w") as f:
            f.write(str(index))
    except Exception as e:
        logger.error(f"❌ Failed to save tweet index: {e}")

# --- Twitter client setup ---
def get_twitter_client():
    try:
        return tweepy.Client(
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_SECRET"),
            wait_on_rate_limit=True
        )
    except Exception as e:
        logger.error(f"❌ Twitter client error: {e}")
        return None

# --- Posting logic ---
def get_next_tweet(tweets):
    index = get_tweet_index()
    tweet = tweets[index % len(tweets)]
    save_tweet_index(index + 1)
    return tweet

def post_tweet():
    global tweet_client, tweet_list

    now = datetime.now()
    if not (9 <= now.hour < 21):
        logger.info("⏱️ Outside 9AM–9PM. Skipping tweet.")
        return

    tweet = get_next_tweet(tweet_list)
    if not tweet:
        logger.error("❌ No tweet available.")
        return

    for attempt in range(1, 4):
        try:
            response = tweet_client.create_tweet(text=tweet)
            logger.info(f"✅ Tweeted: {tweet}")
            logger.info(f"🔗 Tweet ID: {response.data['id']}")
            return
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt}: {e}")
            time.sleep(60 * attempt)

    logger.error("❌ All retries failed.")

# --- Init and schedule ---
def main():
    keep_alive()

    global tweet_client, tweet_list
    tweet_list = load_tweets()
    tweet_client = get_twitter_client()

    if not tweet_list or not tweet_client:
        logger.error("❌ Bot cannot start without tweets or client.")
        return

    # Schedule every 45 minutes
    schedule.every(45).minutes.do(post_tweet)
    logger.info("🚀 Bot started. Posting between 9 AM to 9 PM every ~45 mins.")

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()

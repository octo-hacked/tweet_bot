import os
import time
import schedule
import tweepy
from flask import Flask
from threading import Thread
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app for keep-alive (required for Replit)
app = Flask('')

@app.route('/')
def home():
    return "✅ Tweet bot is running successfully!"

@app.route('/status')
def status():
    return {
        "status": "running",
        "next_tweet": "Every 3 hours",
        "monthly_limit": "500 tweets (Free Tier)"
    }

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True  # Dies when main thread dies
    t.start()

# Twitter API Setup - Use Secrets in Replit instead of .env
def get_twitter_client():
    """Initialize Twitter client with proper error handling"""
    try:
        # Get credentials from environment (Replit Secrets)
        api_key = os.getenv("TWITTER_API_KEY")
        api_secret = os.getenv("TWITTER_API_SECRET") 
        access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        access_secret = os.getenv("TWITTER_ACCESS_SECRET")

        # Validate credentials exist
        if not all([api_key, api_secret, access_token, access_secret]):
            logger.error("❌ Missing Twitter API credentials in environment variables")
            return None

        # Create client with OAuth 1.0a (required for posting on free tier)
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
            wait_on_rate_limit=True  # Automatically handle rate limits
        )

        # Test authentication
        try:
            me = client.get_me()
            if me.data:
                logger.info(f"✅ Successfully authenticated as: @{me.data.username}")
                return client
            else:
                logger.error("❌ Authentication failed - no user data returned")
                return None
        except tweepy.Forbidden as e:
            logger.error(f"❌ Permission error: {e}")
            logger.error("🔧 Check your app permissions in Twitter Developer Portal!")
            logger.error("📋 Make sure you have 'Read and Write' permissions enabled")
            logger.error("🔄 Remember to regenerate tokens AFTER changing permissions")
            return None
        except Exception as e:
            logger.error(f"❌ Authentication test failed: {e}")
            return None

    except Exception as e:
        logger.error(f"❌ Error setting up Twitter client: {e}")
        return None

# Load tweets from file
def load_tweets():
    """Load tweets from file with error handling"""
    try:
        # Updated to use tweet.txt (without 's')
        with open("tweet.txt", "r", encoding="utf-8") as f:
            tweets = [line.strip() for line in f if line.strip()]

        if not tweets:
            logger.error("❌ No tweets found in tweet.txt file")
            return []

        logger.info(f"📝 Loaded {len(tweets)} tweets from tweet.txt")
        return tweets
    except FileNotFoundError:
        logger.error("❌ tweet.txt file not found")
        return []
    except Exception as e:
        logger.error(f"❌ Error loading tweets: {e}")
        return []

# Tweet tracking
def get_tweet_index():
    """Get current tweet index from file"""
    try:
        if os.path.exists("last_index.txt"):
            with open("last_index.txt", "r") as f:
                return int(f.read().strip())
        return 0
    except:
        return 0

def save_tweet_index(index):
    """Save current tweet index to file"""
    try:
        with open("last_index.txt", "w") as f:
            f.write(str(index))
    except Exception as e:
        logger.error(f"❌ Error saving tweet index: {e}")

def get_next_tweet(tweets):
    """Get next tweet from the list"""
    if not tweets:
        return None

    index = get_tweet_index()
    tweet = tweets[index % len(tweets)]

    # Update index for next tweet
    save_tweet_index((index + 1) % len(tweets))

    return tweet

def post_tweet():
    """Post a tweet with comprehensive error handling"""
    # FIXED: Added global declarations
    global tweet_client, tweet_list

    if not tweet_client:
        logger.error("❌ Twitter client not initialized")
        return False

    if not tweet_list:
        logger.error("❌ No tweets available")
        return False

    tweet_text = get_next_tweet(tweet_list)
    if not tweet_text:
        logger.error("❌ Could not get next tweet")
        return False

    try:
        # FIXED: Changed 'client' to 'tweet_client'
        response = tweet_client.create_tweet(text=tweet_text)
        logger.info(f"✅ Tweet posted successfully!")
        logger.info(f"📱 Tweet: {tweet_text}")
        logger.info(f"🔗 Tweet ID: {response.data['id']}")
        return True

    except tweepy.TooManyRequests:
        logger.warning("⚠️ Rate limit exceeded. Will retry later.")
        return False
    except tweepy.Forbidden as e:
        logger.error(f"❌ Permission denied: {e}")
        if "oauth1" in str(e).lower():
            logger.error("🔧 OAuth1 permission error detected!")
            logger.error("📋 Solution steps:")
            logger.error("1. Go to Twitter Developer Portal")
            logger.error("2. Go to your app Settings > User authentication settings")
            logger.error("3. Click 'Edit' and enable OAuth 1.0a")
            logger.error("4. Set App permissions to 'Read and Write'")
            logger.error("5. Save settings")
            logger.error("6. Go to Keys and tokens tab")
            logger.error("7. Regenerate Access Token and Secret")
            logger.error("8. Update your Replit Secrets with new tokens")
        return False
    except tweepy.BadRequest as e:
        logger.error(f"❌ Bad request: {e}")
        if "duplicate" in str(e).lower():
            logger.warning("⚠️ Duplicate tweet detected. Skipping...")
            return True  # Count as success to move to next tweet
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error posting tweet: {e}")
        return False

# Initialize global variables
tweet_client = None
tweet_list = []

def initialize_bot():
    """Initialize the bot with all necessary components"""
    global tweet_client, tweet_list

    logger.info("🚀 Initializing Twitter bot...")

    # Load tweets
    tweet_list = load_tweets()
    if not tweet_list:
        logger.error("❌ Cannot start bot without tweets")
        return False

    # Initialize Twitter client
    tweet_client = get_twitter_client()
    if not tweet_client:
        logger.error("❌ Cannot start bot without valid Twitter client")
        return False

    return True

def main():
    """Main bot execution"""
    # Start keep-alive server
    keep_alive()

    # Initialize bot
    if not initialize_bot():
        logger.error("❌ Bot initialization failed. Exiting...")
        return

    logger.info("✅ Bot initialized successfully!")

    # Post first tweet immediately
    logger.info("📤 Posting initial tweet...")
    post_tweet()

    # Schedule tweets every 3 hours (conservative for 17/day limit)
    # This gives us ~8 tweets per day, well within the 17/day limit
    schedule.every(3).hours.do(post_tweet)
    logger.info("⏰ Scheduled tweets every 3 hours")

    # Run scheduler
    logger.info("🔄 Starting scheduler...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("👋 Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Scheduler error: {e}")
            time.sleep(300)  # Wait 5 minutes on error

if __name__ == "__main__":
    main()
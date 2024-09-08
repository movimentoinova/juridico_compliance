import redis
import json

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Define a function to clean up all chat sessions
def cleanup_all_sessions():
    try:
        # Get all chat sessions
        chat_sessions = redis_client.smembers("chat_sessions")
        for session in chat_sessions:
            session_data = json.loads(session)
            # Remove the session metadata
            redis_client.srem("chat_sessions", session)
            # Remove the actual chat history
            redis_client.delete(session_data["id"])
            print(f"Deleted session: {session_data['id']}")
    except redis.RedisError as e:
        print(f"Error cleaning up sessions: {e}")

# Run the cleanup
cleanup_all_sessions()

print("All sessions have been cleaned up.")

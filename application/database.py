from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Supabase URL and KEY must be set in environment variables")
        self.supabase: Client = create_client(url, key)
    
    def get_client(self):
        return self.supabase

# Global database instance
db = Database()

def get_db():
    return db.get_client()

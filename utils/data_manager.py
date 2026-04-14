import os
from . import db_manager

def get_stored_profile():
    return db_manager.get_db_profile()

def save_profile(profile_data):
    db_manager.save_db_profile(profile_data)

def get_stored_preferences():
    # Legacy wrapper for profile
    return db_manager.get_db_profile()

def save_preferences(preferences):
    # Legacy wrapper for profile
    current = db_manager.get_db_profile() or {}
    current.update(preferences)
    db_manager.save_db_profile(current)

def get_seen_jobs():
    return db_manager.get_all_seen_links()

def save_seen_jobs(links_list):
    for link in links_list:
        db_manager.add_seen_link(link)

def get_user_data():
    return db_manager.get_db_profile()

def save_user_data(data):
    db_manager.save_db_profile(data)

def get_last_run():
    return db_manager.get_db_last_run()

def save_last_run():
    db_manager.save_db_last_run()

import streamlit as st
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import io

# Initialize session state
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None

# Database setup
def init_categories():
    conn = sqlite3.connect('ideas.db')
    c = conn.cursor()
    
    # Check if categories exist
    c.execute('SELECT COUNT(*) FROM categories')
    count = c.fetchone()[0]
    
    # If no categories exist, add default ones
    if count == 0:
        default_categories = [
            "App Idea",
            "Investment Opportunities",
            "Passive Income",
            "Business Idea",
            "Stock Market",
            "Side Hustles",
            "Other"
        ]
        
        for category in default_categories:
            c.execute('INSERT INTO categories (name) VALUES (?)', (category,))
    
    conn.commit()
    conn.close()

# Modify the init_db function to call init_categories
def init_db():
    conn = sqlite3.connect('ideas.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories
                 (id INTEGER PRIMARY KEY, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ideas
                 (id INTEGER PRIMARY KEY, 
                  title TEXT, 
                  content TEXT,
                  image_data BLOB,
                  created_at TIMESTAMP,
                  user_id INTEGER,
                  category_id INTEGER,
                  FOREIGN KEY (user_id) REFERENCES users (id),
                  FOREIGN KEY (category_id) REFERENCES categories (id))''')
    conn.commit()
    conn.close()
    
    # Initialize categories after creating tables
    init_categories()

# Authentication functions
def login_user(username, password):
    conn = sqlite3.connect('ideas.db')
    c = conn.cursor()
    c.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    
    if result and check_password_hash(result[1], password):
        st.session_state.user_id = result[0]
        st.session_state.username = username
        return True
    return False

def register_user(username, password):
    try:
        conn = sqlite3.connect('ideas.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                 (username, generate_password_hash(password)))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

# App layout and navigation
def main():
    st.set_page_config(page_title="4Freedom Ideaspace", layout="wide")
    
    # Sidebar navigation
    with st.sidebar:
        st.image('static/images/logo.png', width=200)
        if st.session_state.user_id:
            st.write(f"Welcome, {st.session_state.username}!")
            if st.button("Logout"):
                st.session_state.user_id = None
                st.session_state.username = None
                st.rerun()
        else:
            auth_option = st.radio("Choose option:", ["Login", "Register"])
            if auth_option == "Login":
                show_login()
            else:
                show_register()

    # Main content
    if st.session_state.user_id:
        show_main_content()
    else:
        st.title("Welcome to 4Freedom Ideaspace")
        st.write("Please login or register to continue.")

def show_login():
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if login_user(username, password):
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def show_register():
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Register"):
            if register_user(username, password):
                st.success("Registration successful! Please login.")
            else:
                st.error("Username already exists")

def show_main_content():
    st.title("4Freedom Ideaspace")
    
    # Tabs for different sections
    tab1, tab2 = st.tabs(["Explore Ideas", "Add New Idea"])
    
    with tab1:
        show_ideas()
    
    with tab2:
        add_new_idea()

def show_ideas():
    conn = sqlite3.connect('ideas.db')
    c = conn.cursor()
    c.execute('''SELECT i.id, i.title, i.content, i.image_data, i.created_at, 
                 u.username, c.name as category_name
                 FROM ideas i 
                 JOIN users u ON i.user_id = u.id
                 JOIN categories c ON i.category_id = c.id
                 ORDER BY i.created_at DESC''')
    ideas = c.fetchall()
    conn.close()

    for idea in ideas:
        with st.container():
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader(idea[1])  # Title
                st.write(f"By: {idea[5]} | Category: {idea[6]}")  # Username and Category
                st.write(idea[2])  # Content
            with col2:
                if idea[3]:  # If there's an image
                    image = Image.open(io.BytesIO(idea[3]))
                    st.image(image, use_column_width=True)
            st.divider()

def add_new_idea():
    conn = sqlite3.connect('ideas.db')
    c = conn.cursor()
    c.execute('SELECT id, name FROM categories')
    categories = c.fetchall()
    conn.close()

    with st.form("new_idea_form"):
        title = st.text_input("Title")
        content = st.text_area("Content")
        category = st.selectbox("Category", options=categories, format_func=lambda x: x[1])
        image = st.file_uploader("Add Image", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("Create Idea"):
            if title and content and category:
                image_data = None
                if image:
                    image_data = image.getvalue()
                
                conn = sqlite3.connect('ideas.db')
                c = conn.cursor()
                c.execute('''INSERT INTO ideas 
                            (title, content, image_data, created_at, user_id, category_id)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (title, content, image_data, datetime.now(), 
                          st.session_state.user_id, category[0]))
                conn.commit()
                conn.close()
                st.success("Idea created successfully!")
                st.rerun()
            else:
                st.error("Please fill in all required fields")

if __name__ == "__main__":
    init_db()
    main() 
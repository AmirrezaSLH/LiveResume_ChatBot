# -*- coding: utf-8 -*-
"""

@author: AmirrezaSLH
"""

import os
import json

from openai import OpenAI

from flask import Flask, request, jsonify
from flask_cors import CORS

import mysql.connector


def read_context():
    
    """Read the context file."""
    
    try:
        with open("personal_summary.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
        
    except FileNotFoundError:
        return "Context file not found."
    

class ChatGPTClient:
    def __init__(self, api_key, model='gpt-4o-mini'):
        
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def prompt_engineer(self, user_query='', context='', general_context='', historical_context = ''):
        
        """Creates a structured prompt for better AI responses."""
        
        prompt = (
            f"GPT (You) Role: {general_context}\n"
            f"Information (About Amirreza Salehi, remember more recent life experiences are more relevant as answers): {context}\n"
            f"History of The Converstation (Between GPT and User): {historical_context}\n"
            f"Answer this question (from the User) in a way that aligns with your role, taking into account the provided information and the context of the previous conversation: {user_query}"
        )
        
        return prompt
    
    def historical_context_engineer(self, history):
        

        historical_context = "\n".join(f"User: {q}\nGPT (You): {r}" for q, r in history)
        return historical_context

    def call_chatgpt(self, query):
        
        """Calls the OpenAI API with the given query."""
        
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": query}],
            model=self.model,
        )
        
        return chat_completion

    def process_question(self, user_query='', context='', general_context='', history = [ ('', '') ]):
        
        """Handles full query processing, including prompt engineering and API call."""
        
        historical_context = self.historical_context_engineer(history)
        prompt = self.prompt_engineer(user_query, context, general_context, historical_context)
        gpt_response = self.call_chatgpt(prompt)
        
        response = gpt_response.choices[0].message.content
        
        return response



#SQL

# MySQL Configuration

class VisitsDatabaseManager:
    def __init__(self, host, user, password, database):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connect_db()

    def connect_db(self):
        """ Establish a connection to the database """
        self.db = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database
        )
        self.cursor = self.db.cursor()

    def log_visitor(self, ip):
        """ Log visitor IP and timestamp """
        try:
            self.cursor.execute("INSERT INTO visitors_log (ip_address) VALUES (%s)", (ip,))
            self.db.commit()
        except mysql.connector.Error as err:
            print(f"Error logging visitor: {err}")

    def update_ip_count(self, ip):
        """ Update visitor count per unique IP """
        try:
            self.cursor.execute("SELECT visit_count FROM ip_count WHERE ip_address = %s", (ip,))
            result = self.cursor.fetchone()

            if result:
                self.cursor.execute("UPDATE ip_count SET visit_count = visit_count + 1 WHERE ip_address = %s", (ip,))
            else:
                self.cursor.execute("INSERT INTO ip_count (ip_address, visit_count) VALUES (%s, 1)", (ip,))

            self.db.commit()
        except mysql.connector.Error as err:
            print(f"Error updating IP count: {err}")

    def get_total_visits(self):
        """ Get total visits count """
        self.cursor.execute("SELECT COUNT(*) FROM visitors_log")
        return self.cursor.fetchone()[0]

    def get_unique_visitors(self):
        """ Get unique visitor count """
        self.cursor.execute("SELECT COUNT(*) FROM ip_count")
        return self.cursor.fetchone()[0]

    def close_connection(self):
        """ Close the database connection """
        self.cursor.close()
        self.db.close()

class ChatbotDatabaseManager:
    def __init__(self, host, user, password, database):
        """Initialize the database connection."""
        self.db_config = {
            "host": host,
            "user": user,
            "password": password,
            "database": database
        }
        self.connect_db()

    def connect_db(self):
        """Establish a connection to the MySQL database."""
        self.connection = mysql.connector.connect(**self.db_config)
        self.cursor = self.connection.cursor(dictionary=True)

    def log_chatbot_interaction(self, user_query, chatbot_response, user_ip):
        """Store chatbot interactions in the database."""
        try:
            sql_query = "INSERT INTO chatbot_logs (user_query, chatbot_response, user_ip) VALUES (%s, %s, %s)"

            self.cursor.execute(sql_query, (user_query, chatbot_response, user_ip))
            self.connection.commit()
        except mysql.connector.Error as err:
            print(f"Error logging interaction: {err}")

    def get_recent_queries(self, user_ip):
        """Fetch past chatbot interactions from the same IP in the last 30 minutes."""
        
    
        try:
            sql_query = """
                SELECT user_query, chatbot_response 
                FROM chatbot_logs 
                WHERE user_ip = %s 
                AND timestamp >= NOW() - INTERVAL 30 MINUTE
                ORDER BY timestamp DESC;
            """
            self.cursor.execute(sql_query, (user_ip,))
            results = self.cursor.fetchall()

            # Extract queries and responses into a list of tuples
            history = [(row["user_query"], row["chatbot_response"]) for row in results]
            return history
        
        except mysql.connector.Error as err:
            print(f"Error retrieving chatbot history: {err}")
            return [ ('', '') ]

    def close_connection(self):
        """Close the database connection."""
        self.cursor.close()
        self.connection.close()

db_chatbot_manager = ChatbotDatabaseManager()

app = Flask(__name__)
# Enable CORS to allow requests from your frontend
CORS(app, origins=["http://chatbot.amirrezaslh.com", "http://amirrezaslh.com", "http://www.amirrezaslh.com"])

@app.route('/chatbot', methods=['POST'])
def chatbot():
    
    
    data = request.get_json()
    user_input = data.get("input", "")
    
    #user_ip = request.remote_addr  # Get user's IP address
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)  # Get real IP
    
    # Get historic queries and responses
    h = db_chatbot_manager.get_recent_queries(user_ip)

    api_key = "Your API Key"
    gpt_client = ChatGPTClient(api_key)
    
    g = "You are GPT. You have to answer HR's (User) questions on behalf of the applicant (Amirreza Salehi), supporting their case. Keep responses direct, concise, and limited to one paragraph. Let HR (User) know they can ask for more details if needed."
    c = read_context()
    
    query_response = gpt_client.process_question(
        user_query=user_input,
        context=c,
        general_context=g,
        history = h
    )
    
    # Log the interaction into MySQL
    db_chatbot_manager.log_chatbot_interaction(user_input, query_response, user_ip)
    
    
    return jsonify({"response": query_response})

db_visitor_manager = VisitsDatabaseManager()

@app.route("/count", methods=["GET"])
def count():
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr) # Get visitor's IP
    db_visitor_manager.log_visitor(user_ip)  # Log the visit
    db_visitor_manager.update_ip_count(user_ip)  # Update visit count


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    
    

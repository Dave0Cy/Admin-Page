from flask import Flask, app, render_template, request, redirect, session, url_for, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import base64
import os
from bson import json_util
from flask_bcrypt import Bcrypt



app2 = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app2.secret_key = "saidfl3022dlksfj"

# Session timeout configuration
app2.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# MongoDB Atlas URI
app2.config["MONGO_URI"] = "mongodb+srv://admin-edu:SurveyAdmin@cluster0.ccn4g.mongodb.net/myDatabase?retryWrites=true&w=majority"

mongo = PyMongo(app2)
bcrypt = Bcrypt(app2)

@app2.route('/')
def home():
    return redirect(url_for('login'))



@app2.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        entered_code = request.form["admin_code"]

        # Look up the admin code in MongoDB (assuming it's stored under _id "admin")
        admin = mongo.db["_admin_"].find_one({"_id": "admin"})

        if admin and bcrypt.check_password_hash(admin["admin_code"], entered_code):
            session["admin_logged_in"] = True
            return redirect(url_for("dashboard"))  # or whatever your dashboard route is
        else:
            flash("Invalid admin code", "danger")

    return render_template("adminlogin.html")



@app2.route('/dashboard')
def dashboard():
    if "admin_logged_in" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app2.route('/edit')
def edit_events():
    if "admin_logged_in" not in session:
        return redirect(url_for("login"))
    events = list(mongo.db.events.find())
    return render_template("input.html", events=events)

@app2.route('/display')
def display():
    try:
        # Fetch all upcoming events from the 'events' collection
        events = list(mongo.db.events.find())
        # Convert ObjectId to string for proper rendering
        for event in events:
            event['_id'] = str(event['_id'])
        return render_template("display.html", events=events)
    except Exception as e:
        print("Error fetching upcoming events:", str(e))
        return "Error loading upcoming events"


@app2.route('/logout')
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

@app2.route('/newsletter')
def newsletter():
    try:
        # Fetch all past events from the 'pastEvents' collection
        events = list(mongo.db.pastEvents.find())
        # Convert ObjectId to string for proper rendering
        for event in events:
            event['_id'] = str(event['_id'])
        return render_template("newsletter.html", events=events)
    except Exception as e:
        print("Error fetching past events:", str(e))
        return "Error loading past events"


@app2.route('/save-event', methods=['POST'])
def save_event():
    if "admin_logged_in" not in session:
        flash("You must be logged in to add an event.", "danger")
        print("User not logged in.")
        return redirect(url_for("login"))

    try:
        # Retrieve form data
        description = request.form.get('description', '')
        date = request.form.get('date', '')
        time = request.form.get('time', '')
        location = request.form.get('location', '')
        is_past = request.form.get('is_past', 'false').lower() == 'true'
        image = request.files.get('image')

        print("Form Data Received:")
        print(f"Description: {description}, Date: {date}, Time: {time}, Location: {location}, Is Past: {is_past}")

        # Check for missing image
        if not image:
            flash('Image is required.', 'danger')
            print("No image provided.")
            return redirect(url_for('edit_events'))

        # Convert image to base64
        image_data = base64.b64encode(image.read()).decode('utf-8')

        # Create event object
        event = {
            'description': description,
            'date': date,
            'time': time,
            'location': location,
            'image': image_data
        }

        # Determine the correct collection based on the event type
        collection_name = 'pastEvents' if is_past else 'events'
        result = mongo.db[collection_name].insert_one(event)

        print(f"Event saved to {collection_name} with ID: {result.inserted_id}")
        flash('Event saved successfully!', 'success')

    except Exception as e:
        print("Error while saving event:", str(e))
        flash("Error saving event.", "danger")

    return redirect(url_for('edit_events'))



@app2.route('/api/events/all', methods=['GET'])
def get_all_events():
    try:
        events = list(mongo.db.events.find())
        past_events = list(mongo.db.pastEvents.find())
        # Convert ObjectId to string for JSON serialization
        for event in events:
            event['_id'] = str(event['_id'])
        for event in past_events:
            event['_id'] = str(event['_id'])
        all_events = events + past_events
        return json_util.dumps(all_events), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        print(f"Error fetching events: {e}")
        return json_util.dumps({"error": "Failed to fetch events"}), 500

@app2.route('/api/events/past', methods=['GET'])
def get_past_events():
    try:
        # Fetch all past events from the 'pastEvents' collection
        events = list(mongo.db.pastEvents.find())
        # Convert ObjectId to string for proper rendering
        for event in events:
            event['_id'] = str(event['_id'])
        return json_util.dumps(events), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        print(f"Error fetching past events: {e}")
        return json_util.dumps({"error": "Failed to fetch past events"}), 500


if __name__ == "__main__":
    app2.run(debug=True)

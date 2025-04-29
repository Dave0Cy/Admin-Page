from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import base64
import os
from bson import json_util
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message

app2 = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app2.secret_key = "saidfl3022dlksfj"

# Session timeout configuration
app2.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# MongoDB Atlas URI
app2.config["MONGO_URI"] = "mongodb+srv://admin-edu:SurveyAdmin@cluster0.ccn4g.mongodb.net/myDatabase?retryWrites=true&w=majority"

mongo = PyMongo(app2)
bcrypt = Bcrypt(app2)

# Hard‐coded mail settings
app2.config.update({
    'MAIL_SERVER':         'smtp.gmail.com',
    'MAIL_PORT':           587,
    'MAIL_USE_TLS':        True,
    'MAIL_USERNAME':       'davidcepeda420@gmail.com',
    'MAIL_PASSWORD':       'bwmy pefi ipms nzwh',
    'MAIL_DEFAULT_SENDER': 'davidcepeda420@gmail.com',
})

mail = Mail(app2)   

def get_recipients():
    emails = set()
    # Users collection
    for u in mongo.db.users.find({'receive noti': {'$ne': 'opt-out'}}, {'email':1}):
        emails.add(u['email'])
    # Survey responses collection (replace 'responses' with your actual name)
    for r in mongo.db.Responses.find({'receive noti': {'$ne': 'opt-out'}}, {'Email':1}):
        emails.add(r['Email'])
    return list(emails)

def send_notification(event_type, context=None):
    # event_type: 'new_event', 'event_updated', 'past_event_added', 'custom'
    setting = mongo.db.emailSettings.find_one({'type': event_type})
    if not setting or not setting.get('enabled'):
        return

    # Fill in placeholders, if any
    subject = setting['subject']
    body_t  = setting['body']
    body    = body_t.format(**(context or {}))

    recipients = get_recipients()
    for addr in recipients:
        msg = Message(subject,
                      sender=app2.config['MAIL_USERNAME'],
                      recipients=[addr])
        msg.body = body
        mail.send(msg)


@app2.route('/')
def home():
    return redirect(url_for('login'))

@app2.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        entered_code = request.form["admin_code"]

        # Look up the admin code in MongoDB (stored under _id "admin")
        admin = mongo.db["_admin_"].find_one({"_id": "admin"})

        if admin and bcrypt.check_password_hash(admin["admin_code"], entered_code):
            session["admin_logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid admin code", "danger")

    return render_template("adminlogin.html")


@app2.route('/dashboard')
def dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app2.route('/banner', methods=['GET', 'POST'])
def banner():
    if not session.get("admin_logged_in"):
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('banner_image')
        if not file:
            flash("Please choose an image to upload", "danger")
            return redirect(url_for('banner'))

        # Read & encode the upload
        img_data = base64.b64encode(file.read()).decode('utf-8')

        # Delete any previous banner docs, then insert this one
        mongo.db.banner.delete_many({})
        mongo.db.banner.insert_one({
            'image': img_data
        })

        flash("Banner updated", "success")
        return redirect(url_for('banner'))

    # GET: fetch the single banner doc (if it exists)
    doc = mongo.db.banner.find_one()
    banner_url = doc['image'] if doc else None

    return render_template('banner.html', banner_url=banner_url)


@app2.route('/edit')
def edit_events():
    if not session.get("admin_logged_in"):
        return redirect(url_for('login'))
    upcoming = list(mongo.db.events.find())
    past     = list(mongo.db.pastEvents.find())
    for e in upcoming: e['_id'] = str(e['_id'])
    for p in past:     p['_id'] = str(p['_id'])
    return render_template('input.html', events=upcoming, past_events=past)


@app2.route('/delete-event/<id>', methods=['POST'])
def delete_event(id):
    if not session.get("admin_logged_in"):  
        return redirect(url_for('login'))
    mongo.db.events.delete_one({'_id': ObjectId(id)})
    flash("Event deleted", 'success')
    return redirect(url_for('edit_events'))

@app2.route('/display')
def display():
    events = list(mongo.db.events.find())
    for ev in events:
        ev['_id'] = str(ev['_id'])
    return render_template("display.html", events=events)


@app2.route('/logout')
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))


@app2.route('/newsletter')
def newsletter():
    events = list(mongo.db.pastEvents.find())
    for ev in events:
        ev['_id'] = str(ev['_id'])
    t = {
        'past_events': 'Past Events',
        'no_past_events': 'No past events.'
    }
    return render_template("newsletter.html", events=events, t=t)

@app2.route('/survey_events')
def survey_events():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    # ← use mongo.db, not db
    events = list(mongo.db.events.find())
    for ev in events:
        ev['_id'] = str(ev['_id'])
    return render_template('dashboard.html', events=events)



@app2.route('/survey_events/<event_id>')
def survey_event_detail(event_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    # ← mongo.db here too
    ev = mongo.db.events.find_one({'_id': ObjectId(event_id)})
    if not ev:
        flash("Event not found.", "danger")
        return redirect(url_for('survey_events'))

    ev['_id'] = str(ev['_id'])
    all_events = list(mongo.db.events.find())
    for e in all_events:
        e['_id'] = str(e['_id'])

    return render_template('dashboard.html', events=all_events, event=ev)

@app2.route('/email-settings', methods=['GET'])
def email_settings():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    # Load whatever’s in the DB:
    docs = mongo.db.emailSettings.find()
    settings = { d['type']: d for d in docs }

    # Ensure all types exist so Jinja never errors:
    for t in ["new_event", "event_updated", "past_event_added", "custom"]:
        if t not in settings:
            settings[t] = {
                "type":    t,
                "enabled": False,
                "subject": "",
                "body":    ""
            }

    return render_template("email_settings.html", settings=settings)

@app2.route('/email-settings/update', methods=['POST'])
def update_email_setting():
    if not session.get("admin_logged_in"):
        return redirect(url_for('login'))
    s_type  = request.form['type']
    subject = request.form['subject']
    body    = request.form['body']
    enabled = 'enabled' in request.form
    mongo.db.emailSettings.update_one(
      {'type': s_type},
      {'$set': {
         'subject': subject,
         'body':    body,
         'enabled': enabled
      }},
      upsert=True
    )
    flash(f"{s_type} settings saved", 'success')
    return redirect(url_for('email_settings'))

@app2.route('/send-custom-email', methods=['POST'])
def send_custom_email():
    if not session.get("admin_logged_in"):
        return redirect(url_for('login'))
    subject = request.form['custom_subject']
    body    = request.form['custom_body']
    # Temporarily store in DB so admin can edit later:
    mongo.db.emailSettings.update_one(
      {'type': 'custom'},
      {'$set': {'subject': subject, 'body': body}},
      upsert=True
    )
    # Send immediately:
    send_notification('custom')
    flash("Custom email sent", 'success')
    return redirect(url_for('email_settings'))

@app2.route('/save-event', methods=['POST'])
def save_event():
    if not session.get("admin_logged_in"):
        flash("Log in first", 'danger')
        return redirect(url_for('login'))

    eid    = request.form.get('event_id')  # hidden field for edits
    desc   = request.form['description']
    desc_es = request.form.get('descriptionSpanish','')
    date   = request.form['date']
    time_  = request.form['time']
    loc    = request.form['location']
    img_f  = request.files.get('image')

    # On create, image is required; on update, it’s optional
    if not eid and not img_f:
        flash("Image required for new event", 'danger')
        return redirect(url_for('edit_events'))

    doc = {
        'description': desc,
        'descriptionSpanish': desc_es,
        'date': date,
        'time': time_,
        'location': loc,
    }
    if img_f:
        img_data = base64.b64encode(img_f.read()).decode('utf-8')
        doc['image'] = img_data

    if eid:
        mongo.db.events.update_one(
            {"_id": ObjectId(eid)},
            {"$set": doc}
        )
        flash("Event updated", "success")
        send_notification("event_updated", {
            "description": desc,
            "date": date,
            "time": time_,
            "location": loc
        })
    else:
        mongo.db.events.insert_one(doc)
        flash("Event created", "success")
        send_notification("new_event", {
            "description": desc,
            "date": date,
            "time": time_,
            "location": loc
        })

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

@app2.route('/save-past-event', methods=['POST'])
def save_past_event():
    if not session.get("admin_logged_in"):
        flash("Log in first", "danger")
        return redirect(url_for("login"))

    eid     = request.form.get("past_event_id")
    desc    = request.form["descriptionPast"]
    desc_es = request.form.get("descriptionSpanishPast", "")
    img_f   = request.files.get("imagePast")

    # require image on create
    if not eid and not img_f:
        flash("Image required for new past event", "danger")
        return redirect(url_for("edit_events"))

    # Build document
    doc = {
        "description": desc,
        "descriptionSpanish": desc_es
    }
    if img_f:
        img_data = base64.b64encode(img_f.read()).decode("utf-8")
        doc["image"] = img_data

    if eid:
        mongo.db.pastEvents.update_one(
            {"_id": ObjectId(eid)},
            {"$set": doc}
        )
        flash("Past event updated", "success")
        send_notification("past_event_added", {"description": desc})
    else:
        mongo.db.pastEvents.insert_one(doc)
        flash("Past event created", "success")
        send_notification("past_event_added", {"description": desc})

    return redirect(url_for("edit_events"))

@app2.route('/delete-past-event/<id>', methods=['POST'])
def delete_past_event(id):
    if not session.get("admin_logged_in"):
        return redirect(url_for('login'))
    mongo.db.pastEvents.delete_one({'_id': ObjectId(id)})
    flash("Past event deleted", 'success')
    return redirect(url_for('edit_events'))


if __name__ == "__main__":
    app2.run()

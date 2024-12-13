from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import quote as url_quote
import sqlite3

#from chart import chart_bp  # Import the chart blueprint

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # Redirects users to login page if not authenticated

# Connect to SQLite database
def connect_db():
    return sqlite3.connect('tracker.db')

# Initialize the database (run this function once to create the table)
def init_db():
    with connect_db() as con:
        # Transactions table with user_id foreign key
        con.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                description TEXT,
                amount REAL,
                category TEXT,
                type TEXT,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        # Users table for authentication
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cur.fetchone()
    if user:
        return User(*user)
    return None



# Sign-up route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        with connect_db() as con:
            cur = con.cursor()
            try:
                cur.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                            (username, email, password_hash))
                con.commit()
                flash("Sign-up successful! Please log in.", "success")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash("Username or email already exists. Please try again.", "danger")
    return render_template('signup.html')




# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with connect_db() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cur.fetchone()

        if user and check_password_hash(user[3], password):  # user[3] is the password_hash
            user_obj = User(*user)
            login_user(user_obj)
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        flash("Invalid email or password. Please try again.", "danger")
    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

# Home page (index)
@app.route('/')
@login_required  # Protect the index page
def index():
    return render_template('index.html', name=current_user.username)

# Add transaction route
@app.route('/add', methods=['POST'])
@login_required
def add_transaction():
    date = request.form['date']
    description = request.form['description']
    amount = request.form['amount']
    category = request.form['category']
    type_ = request.form['type']
    user_id = current_user.id  # Get the logged-in user's ID

    with connect_db() as con:
        cur = con.cursor()
        cur.execute("INSERT INTO transactions (date, description, amount, category, type, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (date, description, amount, category, type_, user_id))
        con.commit()

    return redirect(url_for('view_transactions'))

# View transactions
@app.route('/view')
@login_required
def view_transactions():
    user_id = current_user.id  # Get the logged-in user's ID

    with connect_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = cur.fetchall()
    return render_template('view.html', transactions=transactions)

# Monthly report route
@app.route('/monthly_report')
@login_required
def monthly_report():
    user_id = current_user.id  # Get the logged-in user's ID

    with connect_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
            FROM transactions
            WHERE user_id = ?
            GROUP BY month
            ORDER BY month;
        """, (user_id,))  # Filter by the logged-in user
        monthly_data = cur.fetchall()

    # Prepare data for the report
    labels = [month for month, _ in monthly_data]
    totals = [total for _, total in monthly_data]

    # Handle case when no data is available
    if not labels:  # If there are no labels, create a placeholder
        labels = ['No data']
        totals = [0]

    return render_template('monthly_report.html', labels=labels, totals=totals)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)


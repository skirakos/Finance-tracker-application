from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import openpyxl
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

def connect_db():
    return sqlite3.connect('tracker.db')

def init_db():
    with connect_db() as con:
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
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with connect_db() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cur.fetchone()

        if user and check_password_hash(user[3], password):
            user_obj = User(*user)
            login_user(user_obj)
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        flash("Invalid email or password. Please try again.", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', name=current_user.username)

@app.route('/add', methods=['POST'])
@login_required
def add_transaction():
    date = request.form['date']
    description = request.form['description']
    amount = request.form['amount']
    category = request.form['category']
    type_ = request.form['type']
    user_id = current_user.id

    with connect_db() as con:
        cur = con.cursor()
        cur.execute("INSERT INTO transactions (date, description, amount, category, type, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (date, description, amount, category, type_, user_id))
        con.commit()

    return redirect(url_for('view_transactions'))

@app.route('/view')
@login_required
def view_transactions():
    user_id = current_user.id

    with connect_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = cur.fetchall()
    return render_template('view.html', transactions=transactions)

@app.route('/monthly_report')
@login_required
def monthly_report():
    user_id = current_user.id

    with connect_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
            FROM transactions
            WHERE user_id = ?
            GROUP BY month
            ORDER BY month;
        """, (user_id,))
        monthly_data = cur.fetchall()

    labels = [month for month, _ in monthly_data]
    totals = [total for _, total in monthly_data]

    if not labels:
        labels = ['No data']
        totals = [0]

    return render_template('monthly_report.html', labels=labels, totals=totals)

@app.route('/download_transactions')
@login_required
def download_transactions():
    user_id = current_user.id
    
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = cur.fetchall()

    if not transactions:
        flash("No transactions found for the user.", "warning")
        return redirect(url_for('view_transactions'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"

    column_titles = ["ID", "Date", "Description", "Amount", "Category", "Type"]
    ws.append(column_titles)

    for transaction in transactions:
        ws.append(transaction[1:])

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(file_stream, as_attachment=True, download_name="transactions.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
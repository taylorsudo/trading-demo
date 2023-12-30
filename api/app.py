import os
import redis

from cs50 import SQL
from datetime import datetime, timedelta
from dotenv import load_dotenv  # environment variables
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required, lookup, usd  # .helpers

# Load environment variables
load_dotenv("/workspaces/126066949/project/vercel.env")

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure secret key
# app.secret_key = os.getenv("SECRET_KEY")

# Get environment variables for Postgres
postgres_url = os.getenv("POSTGRES_URL")
if postgres_url.startswith("postgres://"):
    postgres_url = postgres_url.replace("postgres://", "postgresql://")
db = SQL(postgres_url + "?sslmode=require")

# Configure Flask to use the Redis session interface
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False
# app.config['SESSION_USE_SIGNER'] = True
kv_url = os.getenv("KV_URL")
if kv_url.startswith("redis://"):
    kv_url = kv_url.replace("redis://", "rediss://")
app.config["SESSION_REDIS"] = redis.from_url(kv_url)

# Initialise the Flask-Session extension
Session(app)


# Initialise timescale variable
timescale = {
    "1D": 1,
    "5D": 5,
    "1M": 30,
    "6M": 180,
    "YTD": (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
    "1Y": 365,
    "5Y": 5 * 365,
}


def get_timescale_value(key):
    # Get value of timescale key
    num_days = timescale.get(f"{key.upper()}")

    # Return earliest date for the given timescale
    date = datetime.now() - timedelta(days=num_days)
    return date


def get_balance_history(key):
    # Get earliest date from function
    start_date = get_timescale_value(key)

    # Retrieve balance history from earliest to latest
    query = """
        SELECT transacted, balance
        FROM history
        WHERE user_id = :user_id AND transacted >= :start_date
        ORDER BY transacted ASC
    """

    # Get list of dictionaries (hash maps)
    balance_history = db.execute(query, user_id=session["user_id"], start_date=start_date)

    # Pass values into single dictionary
    dictionary = {}
    for transaction in balance_history:
        date_str = transaction["transacted"].strftime("%Y-%m-%d")
        dictionary[date_str] = transaction["balance"]

    return dictionary


def calculate_gains_losses(key):
    balance_history = get_balance_history(key)

    # Initialize gain_loss dictionary to store gain or loss for each date
    gain_loss = {}

    # Get sorted list of dates from balance history
    dates = sorted(balance_history.keys())

    # Calculate gain or loss for each date
    for i in range(len(dates)):
        date = dates[i]
        balance = balance_history[date]

        # Calculate gain or loss for the current date
        if i == 0:
            gain_loss[date] = 0  # Initial date, set gain_loss to 0
        else:
            previous_balance = balance_history[dates[i - 1]]
            gain_loss[date] = balance - previous_balance

    return gain_loss


@app.route('/timescale', methods=['GET'])
@login_required
def jsonify_data():
    tab = request.args.get("tab")
    balance_history = get_balance_history(tab)
    gain_loss = calculate_gains_losses(tab)
    data = {}
    chart_data = {}

    # Add the date and balance to the chart_data dictionary
    for date_str, balance in balance_history.items():
        chart_data[date_str] = balance

    # Add 'gain_loss' and 'chart_data' to the 'data' dictionary
    for date_str, balance in balance_history.items():
        data[tab] = {
            "gain_loss": gain_loss.get(date_str, 0),  # Use get method to handle missing dates
            "chart_data": chart_data
        }

    print(data)

    return jsonify(data)


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    tabs = list(timescale.keys())

    # Get user's portfolio and cash
    rows = db.execute(
        "SELECT * FROM portfolios WHERE user_id = :user_id ORDER BY symbol ASC",
        user_id=session["user_id"],
    )
    cash = db.execute(
        "SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"]
    )

    # Check if cash is not empty before accessing its elements
    cash_value = cash[0]["cash"] if cash else 0
    total = cash_value if cash_value else 0

    # Get stock name, current value, and total value
    for row in rows:
        row["price"] = lookup(row["symbol"])["price"]
        row["total"] = row["price"] * row["shares"]

        # Increment total
        total += row["total"]

    # Render home page
    return render_template(
        "index.html", rows=rows, cash=cash_value, total=total, tabs=tabs
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # If form submitted via POST
    if request.method == "POST":
        # Get form input
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        quote = lookup(symbol)
        transacted = datetime.now().strftime("%F %T.%f")

        # Flash error if input is blank or symbol does not exist
        if quote == None:
            flash("Symbol not found", "danger")
            return redirect("/buy")

        # If shares is digit, convert shares to integer
        if shares.isdigit():
            shares = int(request.form.get("shares"))

        # Else flash error
        else:
            flash("You cannot purchase partial shares", "danger")
            return redirect("/buy")

        # Flash error if number of shares not given
        if not shares:
            flash("Must provide number of shares", "danger")
            return redirect("/buy")

        # Calculate cost of transaction
        cost = quote["price"] * shares

        # SELECT how much cash the user currently has in users
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        balance = balance[0]["cash"]

        # Flash error if balance less than cost
        if balance < cost:
            flash("Insufficient funds", "danger")
            return redirect("/buy")

        # Query database for symbol in portfolio
        row = db.execute(
            "SELECT * FROM portfolios WHERE user_id = ? AND symbol = ?",
            session["user_id"],
            symbol,
        )

        # If symbol exists in portfolio
        if len(row) == 1:
            # Update number of shares
            shares = row[0]["shares"] + shares

            # Update shares in portfolios table
            db.execute(
                "UPDATE portfolios SET shares = ? WHERE user_id = ? AND symbol = ?",
                shares,
                session["user_id"],
                symbol,
            )

        # Else if shares don't yet exist
        else:
            # Insert shares into portfolios table
            db.execute(
                "INSERT INTO portfolios (user_id, symbol, shares) VALUES (?,?,?)",
                session["user_id"],
                symbol,
                shares,
            )

        # Update balance
        balance = balance - cost

        # Update history table
        db.execute(
            "INSERT INTO history (user_id, symbol, shares, price, balance, transacted) VALUES (?,?,?,?,?,?)",
            session["user_id"],
            symbol,
            shares,
            quote["price"],
            balance,
            transacted,
        )

        # Update cash in users table
        db.execute(
            "UPDATE users SET cash = ? where id = ?", balance, session["user_id"]
        )

        # Flash message
        flash(f"Purchased {shares} share(s) of {symbol}", "success")

        # Redirect user to home page
        return redirect("/")

    # Else if form submitted via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY transacted DESC",
        session["user_id"],
    )

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username", "danger")
            return redirect("/login")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password", "danger")
            return redirect("/login")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            flash("Invalid username and/or password", "danger")
            return redirect("/login")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # If form submitted via POST
    if request.method == "POST":
        # Call the lookup function
        symbol = lookup(request.form.get("symbol"))

        # Ensure user provides symbol
        if not symbol:
            flash("Symbol is required", "danger")
            return redirect("/quote")

        # Ensure stock is valid
        elif symbol == None:
            flash("Invalid stock symbol", "danger")
            return redirect("/quote")

        # Display the results
        flash(f"A share of {symbol['symbol']} costs ${symbol['price']}.", "primary")
        return redirect("/quote")

    # Else if requested via GET, display quote form
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # If form submitted via POST
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username", "danger")
            return redirect("/register")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password", "danger")
            return redirect("/register")

        # Ensure password matches confirmation
        elif request.form.get("password") != request.form.get("confirmation"):
            flash("Passwords do not match", "danger")
            return redirect("/register")

        # Store username and password hash
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username doesn't exist
        if len(rows) != 0:
            flash("Username is already taken", "danger")
            return redirect("/register")

        # Insert new user into users table
        db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, hash)

        # Redirect user to home page
        return redirect("/")

    # Else if requested via GET, display registration form
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # If form submitted via POST
    if request.method == "POST":
        # Get user input
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        quote = lookup(symbol)
        transacted = datetime.now().strftime("%F %T.%f")

        # Get user's portfolio
        rows = db.execute(
            "SELECT * FROM portfolios WHERE user_id = ? AND symbol = ?",
            session["user_id"],
            symbol,
        )

        # Ensure symbol exists in portfolio
        if len(rows) != 1:
            flash("Must provide valid stock symbol", "danger")
            return redirect("/sell")

        # Ensure user provides shares
        if not shares:
            flash("Must provide number of shares", "danger")
            return redirect("/sell")

        # Ensure user has enough shares
        if rows[0]["shares"] < shares:
            flash("Insufficient shares", "danger")
            return redirect("/sell")

        # Add total sale value to cash balance
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        balance = balance[0]["cash"] + quote["price"] * shares

        # Update user's cash balance
        db.execute("UPDATE users SET cash = ? WHERE id = ?", balance, session["user_id"])

        # Subtract sold shares from portfolio
        shares = rows[0]["shares"] - shares

        # If shares remain, update portfolio
        if shares > 0:
            db.execute(
                "UPDATE portfolios SET shares = ? WHERE user_id = ? AND symbol = ?",
                shares,
                session["user_id"],
                symbol,
            )

        # Else if no shares remain
        else:
            db.execute(
                "DELETE FROM portfolios WHERE symbol = ? AND user_id = ?",
                symbol,
                session["user_id"],
            )

        # Restore shares value for history
        shares = request.form.get("shares")

        # Update history table
        db.execute(
            "INSERT INTO history (user_id, symbol, shares, price, balance, transacted) VALUES (?,?,?,?,?,?)",
            session["user_id"],
            symbol,
            "-" + shares,
            quote["price"],
            balance,
            transacted,
        )

        # Flash message
        flash(f"Sold {shares} share(s) of {symbol}", "success")

        # Redirect user to home page
        return redirect("/")

    # Else if form submitted via GET
    else:
        # SELECT user's stocks
        portfolio = db.execute(
            "SELECT symbol FROM portfolios WHERE user_id = ?", session["user_id"]
        )

        # Return sell form
        return render_template("sell.html", portfolio=portfolio)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """View account settings."""

    # If form submitted via POST
    if request.method == "POST":
        # Display account page
        return render_template("account.html")

    # Else if requested via GET, display account page
    else:
        return render_template("account.html")


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change password."""

    # If form submitted via POST
    if request.method == "POST":
        # Ensure user provides passwords
        if (
            not request.form.get("old_password")
            or not request.form.get("new_password")
            or not request.form.get("confirm_password")
        ):
            flash("Must provide password", "danger")
            return redirect("/account")

        # Get user input from form
        old = request.form.get("old_password")
        new = request.form.get("new_password")
        confirmation = request.form.get("confirm_password")

        # Get user's previous password
        hash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        hash = hash[0]["hash"]

        # Ensure user inputs correct password
        if not check_password_hash(hash, old):
            flash("Incorrect password", "danger")
            return redirect("/account")

        # If confirmation doesn't match password
        if new != confirmation:
            flash("Passwords do not match", "danger")
            return redirect("/account")

        # Hash new password
        hash = generate_password_hash(new)

        # Update hash in users table
        db.execute("UPDATE users SET hash = ? WHERE id = ?", hash, session["user_id"])

        # Flash message
        flash("Password changed successfully", "success")

        # Return account page
        return redirect("/account")

    # Else if requested via GET, display account page
    else:
        return render_template("account.html")

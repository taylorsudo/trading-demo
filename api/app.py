import os
import redis

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from .helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure secret key
app.secret_key = os.getenv("SECRET_KEY")

# Get environment variables for Postgres
postgres_url = os.getenv("POSTGRES_URL")
if postgres_url.startswith("postgres://"):
    postgres_url = postgres_url.replace("postgres://", "postgresql://")
db = SQL(postgres_url + "?sslmode=require")

# Configure Flask to use the Redis session interface
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False
app.config['SESSION_USE_SIGNER'] = True
kv_url = os.getenv("KV_URL")
if kv_url.startswith("redis://"):
    kv_url = kv_url.replace("redis://", "rediss://")
app.config["SESSION_REDIS"] = redis.from_url(kv_url)

# Initialise the Flask-Session extension
Session(app)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # SELECT user's portfolio and cash
    rows = db.execute(
        "SELECT * FROM portfolios WHERE user_id = ? ORDER BY symbol ASC",
        session["user_id"],
    )
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    # Initialise total
    total = cash[0]["cash"]

    # Get stock name, current value, and total value
    for row in rows:
        row["price"] = lookup(row["symbol"])["price"]
        row["total"] = row["price"] * row["shares"]

        # Increment total
        total += row["total"]

    # Render home page
    return render_template("index.html", rows=rows, cash=cash[0]["cash"], total=total)


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
        transacted = datetime.now().strftime("%F %T.%f")[:-4]

        # Render apology if input is blank or symbol does not exist
        if quote == None:
            return apology("Must provide valid symbol", 400)

        # If shares is digit, convert shares to integer
        if shares.isdigit():
            shares = int(request.form.get("shares"))

        # Else render apology
        else:
            return apology("You cannot purchase partial shares", 400)

        # Render apology if number of shares not given
        if not shares:
            return apology("Must provide number of shares", 400)

        # Calculate cost of transaction
        cost = quote["price"] * shares

        # SELECT how much cash the user currently has in users
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        balance = balance[0]["cash"]

        # Render apology if balance less than cost
        if balance < cost:
            return apology("Insufficient funds", 400)

        # Update history table
        db.execute(
            "INSERT INTO history (user_id, symbol, shares, price, transacted) VALUES (?,?,?,?,?)",
            session["user_id"],
            symbol,
            shares,
            quote["price"],
            transacted,
        )

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

        # Update cash in users table
        db.execute(
            "UPDATE users SET cash = ? where id = ?", balance, session["user_id"]
        )

        # Flash message
        flash(f"Purchased {shares} share(s) of {symbol}")

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
            return apology("Must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("Invalid username and/or password", 400)

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
            return apology("Must provide symbol", 400)

        # Ensure stock is valid
        elif symbol == None:
            return apology("Stock not found", 400)

        # Display the results
        return render_template("quoted.html", symbol=symbol)

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
            return apology("Must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 400)

        # Ensure password matches confirmation
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match", 400)

        # Store username and password hash
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username doesn't exist
        if len(rows) != 0:
            return apology("Username is already taken", 400)

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
        transacted = datetime.now().strftime("%F %T.%f")[:-4]

        # Get user's portfolio
        rows = db.execute(
            "SELECT * FROM portfolios WHERE user_id = ? AND symbol = ?",
            session["user_id"],
            symbol,
        )

        # Ensure symbol exists in portfolio
        if len(rows) != 1:
            return apology("Must provide valid stock symbol", 400)

        # Ensure user provides shares
        if not shares:
            return apology("Must provide number of shares", 400)

        # Ensure user has enough shares
        if rows[0]["shares"] < shares:
            return apology("Insufficient shares", 400)

        # Add total sale value to cash balance
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cash[0]["cash"] + quote["price"] * shares

        # Update user's cash balance
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

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
            "INSERT INTO history (user_id, symbol, shares, price, transacted) VALUES (?,?,?,?,?)",
            session["user_id"],
            symbol,
            "-" + shares,
            quote["price"],
            transacted,
        )

        # Flash message
        flash(f"Sold {shares} share(s) of {symbol}")

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
            return apology("Must provide password", 400)

        # Get user input from form
        old = request.form.get("old_password")
        new = request.form.get("new_password")
        confirmation = request.form.get("confirm_password")

        # Get user's previous password
        hash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        hash = hash[0]["hash"]

        # Ensure user inputs correct password
        if not check_password_hash(hash, old):
            return apology("Incorrect password", 400)

        # If confirmation doesn't match password
        if new != confirmation:
            return apology("Passwords do not match", 400)

        # Hash new password
        hash = generate_password_hash(new)

        # Update hash in users table
        db.execute("UPDATE users SET hash = ? WHERE id = ?", hash, session["user_id"])

        # Flash message
        flash("Password changed successfully")

        # Return account page
        return render_template("account.html")

    # Else if requested via GET, display account page
    else:
        return render_template("account.html")

import os
import redis

from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from .helpers import Database, Timescale, login_required, lookup, usd

# Configure application
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.jinja_env.filters["usd"] = usd

# Configure Flask to use Redis session interface
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False
app.config['SESSION_USE_SIGNER'] = True
kv_url = os.getenv("KV_URL")
if kv_url.startswith("redis://"):
    kv_url = kv_url.replace("redis://", "rediss://")
app.config["SESSION_REDIS"] = redis.from_url(kv_url)

# Initialise the Flask-Session extension
Session(app)
db = Database()
timescale = Timescale()


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    tabs = timescale.get_keys()
    rows = db.get_portfolio()
    cash = db.get_cash()
    total = cash

    for row in rows:
        row["price"] = lookup(row["symbol"])["price"]
        row["total"] = row["price"] * row["shares"]
        total += row["total"]
    total = round(total, 2)

    return render_template(
        "index.html", rows=rows, cash=cash, total=total, tabs=tabs
    )


@app.route('/timescale', methods=['GET'])
@login_required
def get_timescale():
    tab = request.args.get("tab")
    totals_history = db.get_totals_history(tab)
    gain_loss, percent_change = db.get_totals_difference(tab)
    data = {}
    chart_data = {}

    # Add the date and balance to the chart_data dictionary
    for date, balance in totals_history.items():
        chart_data[date] = balance

    # Add 'gain_loss' and 'chart_data' to the 'data' dictionary
    data[tab] = {
        "gain_loss": gain_loss,
        "percent_change": percent_change,
        "chart_data": chart_data
    }

    return data


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Get form input
        symbol = request.form.get("symbol").upper()
        qty = request.form.get("shares")
        quote = lookup(symbol)
        transacted = datetime.now().strftime("%F %T.%f")
        total = db.get_total()

        # Flash error if symbol does not exist
        if not quote:
            flash("Invalid stock symbol", "danger")
            return render_template("buy.html")

        # If shares is digit, convert shares to integer
        if qty.isdigit():
            qty = int(request.form.get("shares"))

        # Else flash error
        else:
            flash("You cannot purchase partial shares", "danger")
            return render_template("buy.html")

        # Calculate cost of transaction
        cost = quote["price"] * qty

        # Select how much cash the user currently has in users
        balance = db.get_cash()

        # Flash error if balance less than cost
        if balance < cost:
            flash("Insufficient funds", "danger")
            return render_template("buy.html")

        # Query database for symbol in portfolio
        row = db.get_shares(symbol)

        # If symbol exists in portfolio
        if len(row) == 1:
            # Update number of shares
            shares = row[0]["shares"] + qty

            # Update shares in portfolios table
            db.update_portfolio(symbol, shares)

        # Else if shares don't yet exist
        else:
            # Insert shares into portfolios table
            db.insert_shares(symbol, qty)

        # Update balance
        balance = balance - cost

        # Update history table
        db.update_history(symbol, qty, quote["price"], total, transacted)

        # Update cash in users table
        db.update_cash(balance)

        # Flash message
        flash(f"Purchased {qty} share(s) of {symbol}", "success")

        # Redirect user to home page
        return redirect("/")

    # Else if form submitted via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.get_history()

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Query database for email
        rows = db.get_user(email)

        # Ensure email address exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], password
        ):
            flash("Invalid email address and/or password", "danger")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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
            flash("Invalid stock symbol", "danger")
            return render_template("quote.html")

        # Display the results
        flash(f"A share of {symbol['symbol']} costs ${symbol['price']}.", "primary")
        return render_template("quote.html")

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

        # Store email and password hash
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        hash = generate_password_hash(password)

        # Ensure password matches confirmation
        if password != confirmation:
            flash("Passwords do not match", "danger")
            return render_template("register.html")

        try:
            db.insert_user(email, hash)

        except:
            flash("Email address is already registered", "danger")
            return render_template("register.html")

        session["user_id"] = db.get_user_id(email)
        flash(f"Welcome to Trading Demo!", "success")
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
        qty = int(request.form.get("shares"))
        quote = lookup(symbol)
        transacted = datetime.now().strftime("%F %T.%f")
        total = db.get_total()

        portfolio_symbol = db.get_shares(symbol)

        # Ensure symbol exists in portfolio
        if len(portfolio_symbol) != 1:
            flash("Must provide valid stock symbol", "danger")
            return render_template("sell.html")

        # Ensure user has enough shares
        if portfolio_symbol[0]["shares"] < qty:
            flash("Insufficient shares", "danger")
            return render_template("sell.html")

        # Add total sale value to cash balance
        balance = db.get_cash()
        balance = balance + quote["price"] * qty

        # Update user's cash balance
        db.update_cash(balance)

        # Subtract sold shares from portfolio
        shares = portfolio_symbol[0]["shares"] - qty

        # If shares remain, update portfolio
        if shares > 0:
            db.update_portfolio(symbol, shares)

        # Else if no shares remain
        else:
            db.delete_shares(symbol)

        # Update history table
        db.update_history(symbol, "-" + str(qty),
        quote["price"], total, transacted)

        # Flash message
        flash(f"Sold {qty} share(s) of {symbol}", "success")

        # Redirect user to home page
        return redirect("/")

    # Else if form submitted via GET
    else:
        # SELECT user's stocks
        portfolio = db.get_symbols()

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
            return render_template("account.html")

        # Get user input from form
        old = request.form.get("old_password")
        new = request.form.get("new_password")
        confirmation = request.form.get("confirm_password")

        # Get hash of user's previous password
        hash = db.get_password()

        # Ensure user inputs correct password
        if not check_password_hash(hash, old):
            flash("Incorrect password", "danger")
            return render_template("account.html")

        # If confirmation doesn't match password
        if new != confirmation:
            flash("Passwords do not match", "danger")
            return render_template("account.html")

        # Hash new password
        hash = generate_password_hash(new)

        # Update hash in users table
        db.update_password(hash)

        # Flash message
        flash("Password changed successfully", "success")

        # Return account page
        return redirect("/account")

    # Else if requested via GET, display account page
    else:
        return render_template("account.html")

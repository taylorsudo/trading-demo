import csv
import os
import pytz
import requests
import urllib
import uuid

from cs50 import SQL
from datetime import datetime, timedelta
from flask import redirect, session
from functools import wraps

# Get environment variables for Postgres
postgres_url = os.getenv("POSTGRES_URL")
if postgres_url.startswith("postgres://"):
    postgres_url = postgres_url.replace("postgres://", "postgresql://")


class Timescale:
    def __init__(self):
        self.timescale = {
            "1D": 1,
            "5D": 5,
            "1M": 30,
            "6M": 180,
            "YTD": (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
            "1Y": 365,
            "5Y": 5 * 365,
        }

    def get_keys(self):
        keys = list(self.timescale.keys())
        return keys

    def get_value(self, key):
        num_days = self.timescale.get(f"{key.upper()}")

        # Return earliest date for the given timescale
        date = datetime.now() - timedelta(days=num_days)
        return date
timescale = Timescale()


class Database:
    def __init__(self):
        self.db = SQL(postgres_url + "?sslmode=require")

    def get_user(self, email):
        rows = self.db.execute(
            "SELECT * FROM users WHERE email = :email",
            email=email
        )
        return rows

    def insert_user(self, email, hash):
        self.db.execute("""INSERT INTO users (email, hash)
        VALUES (?,?)""", email, hash
        )

    def get_user_id(self, email):
        rows = self.db.execute("""SELECT * FROM users
        WHERE email = :email""", email=email
        )
        rows = rows[0]["id"]
        return rows

    def get_password(self):
        rows = self.db.execute("""SELECT hash FROM users
        WHERE id = :user_id""", user_id=session["user_id"]
        )
        rows = hash[0]["hash"]
        return rows

    def update_password(self, hash):
        self.db.execute("""UPDATE users
        SET hash = :hash
        WHERE id = :user_id""",
        hash=hash, user_id=session["user_id"]
        )

    def get_portfolio(self):
        rows = self.db.execute(
            """SELECT * FROM portfolios
            WHERE user_id = :user_id
            ORDER BY symbol ASC""",
            user_id=session["user_id"]
        )
        return rows

    def update_portfolio(self, symbol, shares):
        self.db.execute(
            """UPDATE portfolios SET shares = :shares
            WHERE user_id = :user_id AND symbol = :symbol""",
            shares=shares,
            user_id=session["user_id"],
            symbol=symbol
        )

    def get_shares(self, symbol):
        rows = self.db.execute(
            """SELECT * FROM portfolios
            WHERE user_id = :user_id AND symbol = :symbol""",
            user_id=session["user_id"], symbol=symbol
        )
        return rows

    def get_symbols(self):
        rows = self.db.execute(
            """SELECT symbol FROM portfolios
            WHERE user_id = :user_id""",
            user_id=session["user_id"]
        )
        return rows

    def insert_shares(self, symbol, shares):
        self.db.execute(
            """INSERT INTO portfolios (user_id, symbol, shares)
            VALUES (?,?,?)""",
            session["user_id"],
            symbol,
            shares
        )

    def delete_shares(self, symbol):
        self.db.execute(
            """DELETE FROM portfolios
            WHERE symbol = :symbol AND user_id = :user_id""",
            symbol=symbol,
            user_id=session["user_id"]
        )

    def get_history(self):
        rows = self.db.execute(
            """SELECT * FROM history
            WHERE user_id = :user_id
            ORDER BY transacted DESC""",
            user_id=session["user_id"]
        )
        return rows

    def get_history_timescale(self, key):
        start_date = timescale.get_value(key)
        rows = self.db.execute(
            """SELECT symbol, price, total, transacted
            FROM history
            WHERE user_id = :user_id AND transacted >= :start_date
            ORDER BY transacted ASC""",
            user_id=session["user_id"],
            start_date=start_date
        )
        return rows

    def get_totals_history(self, key):
        rows = self.get_history_timescale(key)
        dictionary = {}
        for row in rows:
            date = row["transacted"].strftime("%Y-%m-%d")
            dictionary[date] = row["total"]
        return dictionary

    def get_totals_difference(self, key):
        rows = self.get_totals_history(key)
        if not rows or len(rows) < 2:
            return 0, 0  # No gain/loss and no percent change

        earliest_value = list(rows.values())[0]
        latest_value = self.get_total()

        gain_loss = latest_value - earliest_value

        percent_change = (gain_loss / earliest_value) * 100

        return gain_loss, percent_change

    def update_history(self, symbol, shares, price, total, transacted):
        self.db.execute(
            """INSERT INTO history (user_id, symbol,
            shares, price, total, transacted)
            VALUES (?,?,?,?,?,?)""",
            session["user_id"],
            symbol,
            shares,
            price,
            total,
            transacted,
        )

    def get_cash(self):
        rows = self.db.execute(
            "SELECT cash FROM users WHERE id = :user_id",
            user_id=session["user_id"]
        )
        rows = rows[0]["cash"]
        return rows

    def update_cash(self, amount):
        self.db.execute(
            "UPDATE users SET cash = :amount where id = :user_id",
            amount=amount, user_id=session["user_id"]
        )

    def get_total(self):
        rows = self.get_portfolio()
        column = self.get_cash()

        for row in rows:
            row["price"] = lookup(row["symbol"])["price"]
            row["total"] = row["price"] * row["shares"]
            column += row["total"]
        return column


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.now(pytz.timezone("US/Eastern"))
    start = end - timedelta(days=7)

    # Yahoo Finance API
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query API
    try:
        response = requests.get(url, cookies={"session": str(uuid.uuid4())}, headers={"User-Agent": "python-requests", "Accept": "*/*"})
        response.raise_for_status()

        # CSV header: Date,Open,High,Low,Close,Adj Close,Volume
        quotes = list(csv.DictReader(response.content.decode("utf-8").splitlines()))
        quotes.reverse()
        price = round(float(quotes[0]["Adj Close"]), 2)
        return {
            "name": symbol,
            "price": price,
            "symbol": symbol
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

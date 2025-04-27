import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import datetime, timezone
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER, user_id NUMERIC NOT NULL, symbol TEXT NOT NULL, \
            shares NUMERIC NOT NULL, price NUMERIC NOT NULL, timestamp TEXT, PRIMARY KEY(id), \
            FOREIGN KEY(user_id) REFERENCES users(id))")
db.execute("CREATE INDEX IF NOT EXISTS orders_by_user_id_index ON orders (user_id)")

if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

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

    owns = own_shares()
    total = 0
    for symbol, shares in owns.items():
        result = lookup(symbol)
        price = result["price"]
        stock_value = shares * price
        total += stock_value
        owns[symbol] = (shares, usd(price), usd(stock_value))
    cash = db.execute("SELECT cash FROM users WHERE id = ? ", session["user_id"])[0]['cash']
    total += cash
    return render_template("index.html", owns=owns, cash= usd(cash), total = usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Put input of user in variables
        buySymbol = request.form.get("symbol")
        buyShares = request.form.get("shares")

        # Use the lookup() function
        buyLookedUp = lookup(buySymbol)

        # Check for user error
        if not buySymbol:
            return apology("missing symbol")
        elif buyLookedUp == None:
            return apology("invalid symbol")
        elif not buyShares:
            return apology("missing shares")
        elif not buyShares.isdigit():
            return apology("invalid shares")

        buyShares = int(buyShares)
        if buyShares <= 0:
            return apology("invalid shares")

        # Set important data to variables
        buyerId = db.execute("SELECT id FROM users WHERE id = ?", session["user_id"])
        buyPrice = buyLookedUp["price"]
        buyTime = datetime.now()

        # Calculate total money spent and set cash of user in a variable
        totalBuyPrice = buyShares * buyPrice
        cashOfBuyer = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # Check if user can afford the stock
        if cashOfBuyer[0]["cash"] < totalBuyPrice:
            return apology("can't afford")
        else:
            remainingCash = int(cashOfBuyer[0]["cash"]) - totalBuyPrice

            db.execute("CREATE TABLE IF NOT EXISTS stocks (id int, symbol char, shares int, price int, total int, time)")
            db.execute("INSERT INTO stocks (id, symbol, shares, price, total, time) VALUES (?, ?, ?, ?, ?, ?)",
                       buyerId[0]["id"], buySymbol, buyShares, buyPrice, totalBuyPrice, buyTime)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", remainingCash, buyerId[0]["id"])
            db.execute("UPDATE stocks SET symbol = UPPER(symbol)")

            flash("Bought!")

            return redirect("/")
    else:
        return render_template("buy.html")
    """if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if '.' or '/' in shares:
            return apology("Invalid number of shares", 400)
        else:
            shares = int(shares)

        if not symbol:
            return apology("Invalid or Blank Ticker", 400)

        stock = lookup(symbol)

        if stock == None:
            return apology("Invalid or Blank Ticker", 400)

        if shares <= 0:
            return apology("0 or negative shares not allowed", 400)


        Price = stock["price"]
        Time = datetime.now()
        transaction_value = shares * Price

        user_id = db.execute("SELECT id FROM users WHERE id = ?", session["user_id"])
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        if user_cash < transaction_value:
            return apology("Insufficient funds")
        else:
            remainingCash = user_cash-transaction_value

            db.execute("INSERT INTO stocks (id, symbol, shares, price, total, time) VALUES(?, ?, ?, ?, ?, ?)", user_id, symbol, shares, Price, transaction_value, Time)
            db.execute("UPDATE users SET cash =? WHERE id = ?", remainingCash, user_id)

    else:
        return render_template("buy.html")"""



@app.route("/history")
@login_required
def history():

    transactions = db.execute("SELECT symbol, price, time FROM stocks WHERE id =?", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

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

    if request.method == "POST":
        symbolFromUser = request.form.get("symbol")
        lookedUp = lookup(symbolFromUser)

        if lookedUp == None:
            return apology("stock symbol does not exist")
        else:
            price = usd(lookedUp["price"])
            symbol = lookedUp["symbol"]
            return render_template("quoted.html", price=price, symbol=symbol)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")
    if username == "" or len(db.execute('SELECT username FROM users WHERE username = ?', username)) > 0:
        return apology("Invalid Username: Blank, or already exists")
    if password == "" or password != confirmation:
        return apology("Invalid Password: Blank, or does not match")

    db.execute('INSERT INTO users (username, hash) \
            VALUES(?, ?)', username, generate_password_hash(password))
    rows = db.execute("SELECT * FROM users WHERE username = ?", username)
    session["user_id"] = rows[0]["id"]
    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    owns = own_shares()
    if request.method == "GET":
        return render_template("sell.html", owns = owns.keys())

    symbol = request.form.get("symbol")
    shares = int(request.form.get("shares"))

    if owns[symbol] < shares:
        return render_template("sell.html", invalid=True, symbol=symbol, owns=owns.keys())

    result = lookup(symbol)
    user_id = session["user_id"]
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]['cash']
    price = result["price"]
    remain = cash + price * shares
    db.execute("UPDATE users SET cash = ? WHERE id = ?", remain, user_id)
    db.execute("INSERT INTO orders (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, ?)", \
                                     user_id, symbol, -shares, price, time_now())
    return redirect("/")


def own_shares():
    user_id = session["user_id"]
    owns = {}
    query = db.execute("SELECT symbol, shares FROM orders WHERE user_id = ?", user_id)
    for q in query:
        symbol, shares = q["symbol"], q["shares"]
        owns[symbol] = owns.setdefault(symbol, 0) + shares

    owns = {k: v for k, v in owns.items() if v != 0}
    return owns

def time_now():
    """HELPER: get current UTC date and time"""
    now_utc = datetime.now(timezone.utc)
    return str(now_utc.date()) + ' @time ' + now_utc.time().strftime("%H:%M:%S")

if __name__ == '__main__':
    app.run(debug=True)

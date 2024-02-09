import datetime
import os
from re import template

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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
    db.execute(
        "DELETE FROM purchases WHERE shares = 0 AND user_id = ?", session["user_id"]
    )
    valores = db.execute(
        "SELECT * FROM purchases WHERE user_id = ?", session["user_id"]
    )
    userdinheiro = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    userdinheiro = float(userdinheiro[0]["cash"])
    totaldinheiro = userdinheiro
    for valor in valores:
        totaldinheiro = totaldinheiro + float(valor["price"] * valor["shares"])
    return render_template(
        "index.html", valores=valores, usuariocash=userdinheiro, total=totaldinheiro
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol valid", 403)

        # Ensure password was submitted
        elif not request.form.get("shares"):
            return apology("must provide shares Valid", 403)

        try:
            shares = int(request.form["shares"])
            if shares <= 0:
                return apology(
                    "Number must be positive"
                )
        except ValueError:
            return apology("Invalid. Insert a number positive")

        valores = lookup(request.form.get("symbol"))
        if valores:
            cashuser = db.execute(
                "SELECT cash FROM users WHERE id = ?", session["user_id"]
            )[0]["cash"]
            compra = float(valores["price"]) * shares

            existing_shares = db.execute(
                "SELECT shares FROM purchases WHERE user_id = ? AND symbol = ?",
                session["user_id"],
                valores["symbol"],
            )
            if existing_shares:
                existing_shares = existing_shares[0]["shares"]
                new_shares = existing_shares + shares

                db.execute(
                    "UPDATE purchases SET shares = ? WHERE user_id = ? AND symbol = ?",
                    new_shares,
                    session["user_id"],
                    valores["symbol"],
                )

            else:
                db.execute(
                    "INSERT INTO purchases (user_id, symbol, price, shares, purchase_date) VALUES (?,?,?,?,?)",
                    session["user_id"],
                    valores["symbol"],
                    float(valores["price"]),
                    shares,
                    datetime.datetime.now(),
                )

            if cashuser >= compra:
                # print(session["user_id"])
                db.execute(
                    "UPDATE users SET cash = cash - ? WHERE id = ?",
                    compra,
                    session["user_id"],
                )
                # history
                db.execute(
                    "INSERT INTO history (user_id, symbol, price, shares, transaction_date, type_transaction) VALUES (?,?,?,?,?,?)",
                    session["user_id"],
                    valores["symbol"],
                    float(valores["price"]),
                    shares,
                    datetime.datetime.now(),
                    "purchase",
                )

            else:
                return apology("Cant be finisher the buy")
            return redirect("/")
        else:
            return apology("Invalid Symbol", 400)
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    valores = db.execute("SELECT * FROM history")
    return render_template("history.html", valores=valores)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 403)

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
        if not request.form.get("symbol"):
            return apology("Provide name valid", 400)

        valores = lookup(request.form.get("symbol"))

        if not valores:
            return apology("Invalid Symbol", 400)
        else:
            acao = valores["symbol"]
            valor = float(valores["price"])
            return render_template("quoted.html", acao=acao, valor=valor)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("Must provide password", 400)

        user = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if password != confirmation:
            return apology("retype confirmation", 400)

        checar_user = db.execute("SELECT * FROM users WHERE username = ?", user)
        if checar_user:
            return apology("Username already in use", 400)

        phash = generate_password_hash(password, method="pbkdf2", salt_length=16)
        db.execute("INSERT INTO users (username,hash) VALUES (?,?)", user, phash)

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Must select a symbol valid", 400)
        if not request.form.get("shares"):
            return apology("Must provide a share valid", 400)
        try:
            shares = int(request.form["shares"])
            if shares <= 0:
                return apology(
                    "The number of shares must be positive", 400
                )
        except ValueError:
            return apology("Invalid. Insert a number positive", 400)

        symbol = request.form.get("symbol")
        existing_shares = db.execute(
            "SELECT shares FROM purchases WHERE user_id = ? AND symbol = ?",
            session["user_id"],
            symbol,
        )
        if not existing_shares:
            return apology("You cant shares of this symbol to sell", 400)

        existing_shares = int(existing_shares[0]["shares"])
        if existing_shares >= shares:
            db.execute(
                "UPDATE purchases SET shares = shares - ? WHERE user_id = ? AND symbol = ?",
                shares,
                session["user_id"],
                symbol,
            )

            # Valor atual
            consulta = lookup(symbol)
            if consulta:
                valoratual = float(consulta["price"]) * shares
                db.execute(
                    "UPDATE users SET cash = cash + ? WHERE id = ?",
                    valoratual,
                    session["user_id"],
                )

                db.execute(
                    "INSERT INTO history (user_id, symbol, price, shares, transaction_date, type_transaction) VALUES (?,?,?,?,?,?)",
                    session["user_id"],
                    symbol,
                    float(consulta["price"]),
                    -1 * shares,
                    datetime.datetime.now(),
                    "sale",
                )
            else:
                return apology("Shares insufficients", 400)
        else:
            return apology("You cant shares of this symbol to sell", 400)

        return redirect("/")

    valores = db.execute(
        "SELECT * FROM purchases WHERE user_id = ?", session["user_id"]
    )
    return render_template("sell.html", valores=valores)
 

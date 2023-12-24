# Trading Simulator

Trade stocks risk-free with Trading Simulator. Practice and learn investment strategies in a realistic environment. Explore finance, monitor live stock prices, and make informed decisions for portfolio growth. Trading Simulator helps you refine trading skills and gain insights into the stock market.

[Preview of Problem Set 9 Solution: CS50 Finance](api/static/screenshot.png)

## CS50 Finance Solution

Adapted from CS50's Problem Set 9, Trading Simulator (or CS50 Finance) is web app implemented with Flask via which you can manage portfolios of stocks. Not only does this tool allow you to check real stocks' actual prices and portfolios' values, it also lets you "buy" and "sell" stocks by querying for stocks' prices.

This version of CS50 Finance has been modified for deployment to Vercel, as Heroku no longer offers free plans.

## How to deploy to Vercel

The following guide was adapted from [David Malan's guide on deploying to Heroku](https://cs50.readthedocs.io/heroku/).

1. Watch [Brian's seminar](https://youtu.be/MJUJ4wbFm_A) to learn about `git` and GitHub, if not already familiar.

1. Create a new **private** repository at <https://github.com/new> (called, e.g., `finance`).

1. Take note of the **HTTPS** URL of the repository (e.g., `https://github.com/username/finance.git`, where `username` is your own GitHub username).

1. Change to your `finance` directory in [Visual Studio Code](https://cs50.readthedocs.io/code/) or [CS50 IDE](https://cs50.readthedocs.io/ide/), as via `cd`.

1. (Codespace users only) Copy your finance project files to `workspaces/finance`.

    Create a folder named `finance` under `workspaces` directory by running

    ```
    mkdir /workspaces/finance
    ```

    Copy your finance project files to `/workspaces/finance` by running

    ```
    cp -r * /workspaces/finance
    ```

    Then change your directory to `/workspaces/finance` by running

    ```
    cd /workspaces/finance
    ```

    Run `ls` to ensure all files have been copied over successfully.

1. Create a `git` repo therein.

    ```
    git init
    ```

1. Add the GitHub repository as a "remote," where `USERNAME` is your own GitHub username.

    ```
    git remote add origin git@github.com:USERNAME/finance.git
    ```

1. In the `requirements.txt` file inside of your `finance` directory, add `pytz`, `psycopg2-binary`, `redis`, and `Werkzeug==2.3.7`, each on separate lines. Your file should then resemble:

    ```
    cs50
    Flask
    Flask-Session
    pytz
    psycopg2-binary
    redis
    requests
    Werkzeug==2.3.7
    ```

1. Push your code to GitHub.

    ```text
    git add -A
    git commit -m "first commit"
    git branch -M main
    git push -u origin main
    ```
    If you visit `https://github.com/username/finance`, where `username` is your own GitHub username, you should see your code in the repository.

1. Sign up for a free Vercel account at <https://vercel.com/signup>, if you don't have one already.

1. Click the **New Project** button and follow the steps to connect your GitHub repository.

From your Vercel dashboard, navigate to "Storage" and create two databases: a Postgres Database, and a KV Database. These will store your users' account and session data, respectively. Choose whichever names you want, as they don't really matter. From each database, copy the URLs beginning with `postgres://` and `redis://`.

1. From your Vercel dashboard, navigate to **Storage** and click **Create Database**. Select **Postgres** and choose a name for your database. This database will store your users' account data.

1. Navigate to back to **Storage** and click **Create Database** once again. Select **Vercel KV** and choose a name for your database. This database will store your users' session data.

1.  In Visual Studio Code or CS50 IDE, open `app.py` in `finance/` and replace

    ```py
    db = SQL("sqlite:///finance.db")
    ```

    with

    ```py
    postgres_url = os.getenv("POSTGRES_URL")
    if postgres_url.startswith("postgres://"):
        postgres_url = postgres_url.replace("postgres://", "postgresql://")
    db = SQL(postgres_url + "?sslmode=require")
    ```

    so that the CS50 Library will connect to your PostgreSQL database instead of your SQLite database. 
    
    Additionally, replace 
    
    ```py
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    Session(app)
    ```

    with

    ```py
    app.config["SESSION_TYPE"] = "redis"
    app.config["SESSION_PERMANENT"] = False
    app.config['SESSION_USE_SIGNER'] = True
    kv_url = os.getenv("KV_URL")
    if kv_url.startswith("redis://"):
        kv_url = kv_url.replace("redis://", "rediss://")
    app.config["SESSION_REDIS"] = redis.from_url(kv_url)
    ```
    
    so that Flask sessions use Redis instead of filesystem. Be sure to add

    ```py
    import os
    import redis
    ```

    atop `app.py`, if not there already.

1.  In Visual Studio Code or CS50 IDE, execute the below to import `finance.db` into your PostgreSQL database, where `URI` is that same URI. Be sure to append `?sslmode=allow` to the URI. Note that disabling SSL's certification verification with `--no-ssl-cert-verification` is not recommended in general but seems to be a [temporary workaround](https://github.com/dimitri/pgloader/commit/16dda01f371f033e0df75d80127643605df7830f).

    ```
    pgloader --no-ssl-cert-verification finance.db URI?sslmode=allow
    ```

    Thereafter, if you'd like to browse or edit your PostgreSQL database, you can use Adminer (a tool like phpLiteAdmin for PostgreSQL databases), at [adminer.cs50.net](https://adminer.cs50.net/). Log in using your Postgres database's credentials from Vercel.

1.  Create a new folder in Visual Studio Code or CS50 IDE called `api` in `finance/` and move your `static` and `templates` folders, as well as `app.py` and `helpers.py` into it.

1.  Create a new file in Visual Studio Code or CS50 IDE called `vercel.json` in `finance/` whose contents are:

    ```json
    {
        "builds": [
            {
                "src": "api/app.py",
                "use": "@vercel/python"
            }
        ],
        "routes": [
            {
                "src": "/(.*)",
                "dest": "api/app.py"
            }
        ]
    }
    ```

   That file will tell Vercel to look in a file called `app.py` for a variable called `app` and serve it with Python.

1.  Push your changes to GitHub.

    ```text
    git add -A
    git commit -m "Add vercel.json"
    git push
    ```

If you visit `https://app-name.vercel.app/`, where `app-name` is your Vercel app's name, you should see your app. If you instead see some error, go to your Vercel dashboard and navigate to **Logs** to diagnose. Each time you add (new or changed) files to your repository and push to GitHub hereafter, your app will be re-deployed to Vercel.

import os
import psycopg2
import datetime
import pandas as pd
from ast import literal_eval


def timestr():
    return (
        datetime.datetime.utcnow()
        .replace(tzinfo=datetime.timezone.utc, microsecond=0)
        .isoformat(sep=" ")[:-3]
    )


def query(sql_query):

    status = 200
    message = ''
    data = None

    # query database
    try:
        conn = psycopg2.connect(
            database='gbd2019',
            host='postgres', # localhost
            user='lemur',
            password='tx*Oj3HjwAlNbNY0XrY3288E#',
        )
        df = pd.read_sql(sql_query, conn)
        conn.close()
    except:
        return {
            "status": 500,
            "message": "Internal Server Error: Error returned from PostgreSQL server on SELECT.",
            "timestamp": timestr(),
            "data": None
        }

    if status == 200:
        if df.shape[0] == 0:
            return {
                "status": status,
                "message": "OK: No data match this query.",
                "timestamp": timestr(),
                "data": None,
            }
        else:
            return {
                "status": status,
                "message": "OK: Data successfully selected from database.",
                "timestamp": timestr(),
                "data": df.to_json()
            }


def check_args(args, required=[], required_oneof=[], optional=[]):
    """Check arguments of GET request
    Args:
        args (dict): Arguments of GET request
        required (list): Names of required arguments
        required_oneof (list): Names of required arguments for which at least one is required
        optional (list): Names of optional arguments
    Returns:
        dict: http response compatible with json format along with modified args object
    """

    # argument lists
    # unlisted arguments: token
    required_globally = []  # 'valid'

    integer_args = ['age', 'year']
    json_args = []
    boolean_args = []
    date_args = []
    list_args = ['region']
    quote_args = ['sex'] + json_args + date_args

    sex_allowed = ['both', 'male', 'female']
    age_allowed = [0, 1, *range(5, 100, 5)]
    year_allowed = [*range(1990, 2016, 5), 2019]

    # initialize response
    status = 200
    message = ""

    # remove unused arguments
    args = {
        key: value
        for key, value in args.items()
        if key in required + required_oneof + optional
    }

    # run checks
    for i in required_globally:
        if not i in required:
            required.append(i)
    if not all(i in args for i in required):
        status = 400
        message = "Bad Request: All of these arguments are required {}.".format(
            required
        )

    elif len(required_oneof) > 0 and not any(i in args for i in required_oneof):
        status = 400
        message = (
            "Bad Request: At least one of these arguments are required {}.".format(
                required_oneof
            )
        )

    elif not all(
        isinstance(args.get(i), int) for i in set(args).intersection(integer_args)
    ):
        for i in set(args).intersection(integer_args):
            try:
                int(float(args.get(i)))
            except:
                status = 400
                message = "Bad Request: '{}' cannot be coerced to an integer.".format(i)
                break

    elif not all(
        isinstance(args.get(i), list) for i in set(args).intersection(list_args)
    ):
        for i in set(args).intersection(list_args):
            try:
                args[i] = literal_eval(args.get(i))
                if not isinstance(args[i], list):
                    args[i] = [args[i]]
                if not isinstance(args[i], list):
                    raise Exception
            except:
                status = 400
                message = "Bad Request: '{}' cannot be coerced to a list. Try {}=['{}'].".format(i, i, args[i])
                break

    elif not all(
        isinstance(args.get(i), datetime.date)
        for i in set(args).intersection(date_args)
    ):
        for i in set(args).intersection(date_args):
            try:
                datetime.datetime.strptime(args.get(i), "%Y-%m-%d")
            except:
                status = 400
                message = "Bad Request: '{}' cannot be coerced to a date of format YYYY-MM-DD.".format(
                    i
                )
                break

    if status == 200:

        # strings to boolean
        for i in boolean_args:
            if i in args and not isinstance(args.get(i), bool):
                args[i] = str(args.get(i)).lower() in [
                    "true",
                    "t",
                    "yes",
                    "y",
                    "on",
                    "1",
                ]

        # quote strings
        for i in set(args).intersection(quote_args):
            args[i] = "'" + str(args[i].replace("'", '"')) + "'"

    return {"status": status, "message": message, "args": args}


def validate_token(token, access="read"):
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        database="gbd2019",
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
    )
    cur = conn.cursor()
    sql_query = (
        "SELECT id, " + access + " FROM users WHERE token='{}';".format(token)
    )
    cur.execute(sql_query)
    conn.commit()
    response = cur.fetchall()

    if len(response) > 0:
        contributor_id = str(response[0][0])
        authenticated = response[0][1]
        cur.execute(
            "UPDATE contributors SET reqs_total=reqs_total+1, reqs_today=reqs_today+1 WHERE id="
            + contributor_id
            + ";"
        )
        conn.commit()
    else:
        contributor_id = None
        authenticated = False

    if authenticated:
        status = 200
        message = "OK: Token successfully authenticated for " + access + " access."
    else:
        status = 401
        message = "Unauthorized: Token failed authentication for " + access + " access."

    conn.close()
    return {"status": status, "message": message, "user_id": contributor_id}



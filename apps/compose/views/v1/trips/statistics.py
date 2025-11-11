from django.db import connection

from apps.compose.models import BusinessTrip


def trips_by_status(start_date=None, end_date=None):
    """
    This function retrieves the count of business trips grouped by their status.
    It returns a dictionary where the keys are the status names
    and the values are the counts of trips in each status.
    """
    query = """
            SELECT bt.trip_status, COUNT(*) AS count
            FROM compose_businesstrip bt
                     JOIN compose_compose cc ON bt.notice_id = cc.id
            WHERE cc.is_signed = TRUE
            """

    if start_date and end_date:
        query += " AND bt.created_date::date BETWEEN %(start_date)s AND %(end_date)s "

    query += " GROUP BY bt.trip_status"

    params = {
        'start_date': start_date,
        'end_date': end_date
    }

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        status_counts = {row[0]: row[1] for row in rows}
    return status_counts


def trips_by_route(start_date=None, end_date=None):
    """
    Generates a dictionary of the count of trips grouped by route for the specified date range.

    Routes can be by car, by plane or by train, etc.
    This function aggregates the number of trips for each route within the specified date range.

    Arguments:
        start_date (Optional[datetime.date]): The starting date of the range to filter trips. Defaults to None.
        end_date (Optional[datetime.date]): The ending date of the range to filter trips. Defaults to None.

    Returns:
        Dict[str, int]: A dictionary where the keys are routes (as strings) and the values are the counts of trips (as integers)
        for each route in the specified date range. If no date range is provided, it returns a count for all routes.

    Raises:
        None: This function does not explicitly raise any exceptions.
    """
    query = """
            SELECT route, COUNT(*) AS count
            FROM compose_businesstrip
            WHERE trip_status = 'reporting'
            """

    if start_date and end_date:
        query += " AND created_date::date BETWEEN %(start_date)s AND %(end_date)s "

    query += "GROUP BY route"

    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        status_counts = {row[0]: row[1] for row in rows}
    return status_counts


def trips_by_top_departments(start_date=None, end_date=None):
    """
    Fetches the top 10 departments with the highest number of business trips
    within an optional specified date range.

    This function retrieves department names and their corresponding counts of business trips
    from the database. If a date range is provided, it filters results to include only trips
    created within the specified range. The results are limited to the top 10 departments
    with the highest number of trips, sorted in descending order of trip count.

    Parameters:
        start_date (Optional[datetime.date]): The start date to filter business trips. Defaults to None.
        end_date (Optional[datetime.date]): The end date to filter business trips. Defaults to None.

    Returns:
        Dict[str, int]: A dictionary where keys are department names, and values are the respective counts of business trips.

    Raises:
        Exception: If the database query execution fails or connection issues occur.
    """
    query = """
            SELECT d.name   AS department_name,
                   COUNT(*) AS trip_count
            FROM compose_businesstrip bt
                     JOIN user_user u ON bt.user_id = u.id
                     JOIN compose_tripverification cv ON bt.id = cv.trip_id
                     LEFT JOIN company_department d ON u.top_level_department_id = d.id
            WHERE bt.trip_status = 'reporting'

            """

    if start_date and end_date:
        query += " AND bt.created_date::date BETWEEN %(start_date)s AND %(end_date)s "

    query += " GROUP BY d.name ORDER BY trip_count DESC LIMIT 10"
    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    data = []
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        for row in rows:
            data.append({
                'name': row[0],
                'count': row[1]
            })

    return data


def trips_line_graph_by_type(start_date):
    """
    Fetch and organize data for trips as a line graph grouped by type over a 12-month period.

    This function retrieves trip data from the database using an SQL query which selects
    the count of trips grouped by their type and month over the last 12 months from the
    current date. The data is then reshaped into a nested dictionary with months as the
    keys mapping to inner dictionaries of trip types and respective counts.

    Args:
        start_date: The starting date for the query filtering. Should be provided as a
        datetime object or a string properly formatted for database usage.

    Returns:
        dict: Nested dictionary where keys are months (formatted as 'YYYY-MM'), and
        values are dictionaries mapping trip types to their respective counts.
    """
    query = """
            WITH months AS (SELECT TO_CHAR(date_trunc('month', gs), 'YYYY-MM') AS month_label,
                                   date_trunc('month', gs)                     AS month_start
                            FROM generate_series(
                                         %(start_date)s::date,
                                         date_trunc('year', %(start_date)s::date) + INTERVAL '11 months',
                                         INTERVAL '1 month'
                                 ) AS gs),
                 trip_data AS (SELECT DATE_TRUNC('month', cb.start_date) AS trip_month,
                                      cb.trip_type,
                                      COUNT(*)                           AS count
                               FROM compose_businesstrip cb
                               WHERE cb.start_date >= %(start_date)s::date
                                 AND cb.start_date < (%(start_date)s::date + INTERVAL '1 year')
                                 AND cb.trip_status = 'reporting'
                               GROUP BY trip_month, cb.trip_type)
            SELECT TO_CHAR(m.month_start, 'YYYY-MM') AS month,
                   t.trip_type,
                   COALESCE(t.count, 0)              AS count
            FROM months m
                     CROSS JOIN (SELECT unnest(ARRAY ['local', 'foreign']) AS trip_type) types
                     LEFT JOIN trip_data t
                               ON t.trip_month = m.month_start AND t.trip_type = types.trip_type
            ORDER BY month, trip_type
            """

    with connection.cursor() as cursor:
        cursor.execute(query, {'start_date': start_date})
        rows = cursor.fetchall()

    # Reshape to nested dict
    result = {}
    for month, trip_type, count in rows:
        if month not in result:
            result[month] = {'local': 0, 'foreign': 0}
        result[month][trip_type] = count

    return result


def trips_by_locations(start_date=None, end_date=None, type=None):
    """
    Fetches the count of business trips grouped by their locations.

    This function retrieves the number of business trips for each location
    within an optional specified date range. It returns a dictionary where
    the keys are location names and the values are the counts of trips in each location.

    Parameters:
        start_date (Optional[datetime.date]): The start date to filter business trips. Defaults to None.
        end_date (Optional[datetime.date]): The end date to filter business trips. Defaults to None.

    Returns:
        Dict[str, int]: A dictionary where keys are location names, and values are the respective counts of business trips.
    """
    query = """
            SELECT r.name                              AS region_name,
                   COUNT(DISTINCT btl.businesstrip_id) AS trip_count
            FROM compose_businesstrip_locations btl
                     JOIN reference_region r ON btl.region_id = r.id
                     JOIN compose_businesstrip cb on cb.id = btl.businesstrip_id
                     JOIN compose_tripverification cv ON btl.businesstrip_id = cv.trip_id
            WHERE cb.trip_type = %(type)s
              AND cb.trip_status = 'reporting'

            """

    if start_date and end_date:
        query += " AND cb.created_date::date BETWEEN %(start_date)s AND %(end_date)s "

    query += " GROUP BY r.name ORDER BY trip_count DESC"

    params = {
        'start_date': start_date,
        'end_date': end_date,
        'type': type
    }
    data = []
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        for row in rows:
            data.append({
                'name': row[0],
                'count': row[1]
            })

    return data


def trips_by_goals(start_date=None, end_date=None):
    """
    Fetches the count of business trips grouped by their goals.

    This function retrieves the number of business trips for each goal
    within an optional specified date range. It returns a dictionary where
    the keys are goal names and the values are the counts of trips in each goal.

    Parameters:
        start_date (Optional[datetime.date]): The start date to filter business trips. Defaults to None.
        end_date (Optional[datetime.date]): The end date to filter business trips. Defaults to None.

    Returns:
        Dict[str, int]: A dictionary where keys are goal names, and values are the respective counts of business trips.
    """
    query = """
            SELECT t.name   AS goal_name,
                   COUNT(*) AS trip_count
            FROM compose_businesstrip_tags btg
                     JOIN compose_tag t ON btg.tag_id = t.id
                     JOIN compose_businesstrip cb on cb.id = btg.businesstrip_id
            WHERE cb.trip_status = 'reporting'

            """

    if start_date and end_date:
        query += " AND cb.created_date::date BETWEEN %(start_date)s AND %(end_date)s "

    query += " GROUP BY t.name ORDER BY trip_count DESC"

    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    data = []
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        for row in rows:
            data.append({
                'name': row[0],
                'count': row[1]
            })

    return data


def trip_expense_line_graph(start_date):
    query = """
            WITH months AS (SELECT generate_series(
                                           DATE_TRUNC('month', %(start_date)s::date),
                                           DATE_TRUNC('month', %(start_date)s::date) + INTERVAL '11 months',
                                           INTERVAL '1 month'
                                   ) AS month_start),
                 pay_type_list AS (SELECT id, name
                                   FROM hr_payrollsubcategory
                                   WHERE id = 25),
                 payroll_data AS (SELECT DATE_TRUNC('month', period) AS payroll_month,
                                         pay_type_id,
                                         SUM(amount)                 AS total_amount
                                  FROM hr_payroll
                                  WHERE period >= %(start_date)s::date
                                    AND period < (%(start_date)s::date + INTERVAL '1 year')
                                    AND pay_type_id = 25
                                  GROUP BY payroll_month, pay_type_id)
            SELECT TO_CHAR(m.month_start, 'YYYY-MM') AS month,
                   pt.name                           AS pay_type_name,
                   COALESCE(p.total_amount, 0)       AS amount
            FROM months m
                     CROSS JOIN pay_type_list pt
                     LEFT JOIN payroll_data p
                               ON p.payroll_month = m.month_start AND p.pay_type_id = pt.id
            ORDER BY month

            """
    with connection.cursor() as cursor:
        cursor.execute(query, {'start_date': start_date})
        rows = cursor.fetchall()
    # Reshape to nested dict
    result = {}
    for month, pay_type_name, amount in rows:
        if month not in result:
            result[month] = {}
        result[month][pay_type_name] = amount
    return result

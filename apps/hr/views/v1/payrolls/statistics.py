from collections import defaultdict

from django.db import connection
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import views
from rest_framework.response import Response

from apps.hr.serializers.v1.payrolls import (
    PayrollSummaryResponseSerializer,
)


def get_payroll_summary(start_date, end_date):
    """
    Retrieves a summary of payroll information, aggregating the data by office type
    and payroll category, and organizes it into a dictionary grouped by office type.

    Returns:
        dict: A dictionary where the keys are office types ('Main office' or
        'Branches') and the values are lists of dictionaries. Each dictionary in the
        list contains 'pay_type' (str) and 'amount' (float) representing payroll
        category and total amount respectively.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT CASE
                                  WHEN company.is_main = TRUE THEN 'head_office'
                                  ELSE 'branches'
                                  END         AS office_type,
                              pc.name         AS pay_type,
                              SUM(hrp.amount) AS amount,
                              pc.id           AS pay_type_id
                       FROM hr_payroll hrp
                                INNER JOIN hr_payrollsubcategory psc ON hrp.pay_type_id = psc.id
                                INNER JOIN hr_payrollcategory pc ON psc.category_id = pc.id
                                INNER JOIN company ON hrp.company_id = company.id
                       WHERE hrp.period BETWEEN %s AND %s
                       GROUP BY office_type, pc.name, pc.id
                       ORDER BY office_type, pc.name
                       """, [start_date, end_date])
        rows = cursor.fetchall()

    result = defaultdict(list)
    for office_type, pay_type, amount, pay_type_id in rows:
        result[office_type].append({
            'pay_type': pay_type,
            'amount': amount,
            'pay_type_id': pay_type_id
        })

    return dict(result)


class PayrollSummaryView(views.APIView):
    """
    Handles HTTP GET requests to provide payroll summary within a specified date range.

    The PayrollSummaryView class processes and responds to API requests for payroll
    summaries. Users must provide a start date and an end date in the query string
    parameters when making requests. The class leverages `get_payroll_summary` to
    retrieve summarized data for the given date range.

    Attributes:
        start_date: Defines the 'start_date' query parameter. It is a required
            parameter of string type and should be in 'YYYY-MM-DD' format.
        end_date: Defines the 'end_date' query parameter. It is a required parameter
            of string type and should be in 'YYYY-MM-DD' format.
        response: Specifies the response structure using
            PayrollSummaryResponseSerializer for successful requests.

    Methods:
        get(request, *args, **kwargs):
            Handles the HTTP GET request to retrieve the payroll summary for the
            provided date range.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="Enter start date in YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=True)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="Enter end date in YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING, required=True)

    response = openapi.Response('response description', PayrollSummaryResponseSerializer)

    @swagger_auto_schema(manual_parameters=[start_date, end_date], responses={200: response})
    def get(self, request, *args, **kwargs):
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        summary = get_payroll_summary(start_date, end_date)
        return Response(summary)


def get_comparison_summary(current_start, current_end, compare_start=None, compare_end=None):
    """
    Fetches and returns a structured summary comparing payroll amounts
    for the current and optional comparison periods, grouped by office
    type and payment type.

    The function queries a database to compute the sum of payroll
    amounts for the specified periods. It processes and organizes
    the results into a dictionary grouped by `head_office` and
    `branches`, enabling detailed analysis of payroll data.

    Parameters:
        current_start (datetime): Start date of the current period.
        current_end (datetime): End date of the current period.
        compare_start (Optional[datetime]): Start date of the comparison period.
            Defaults to None.
        compare_end (Optional[datetime]): End date of the comparison period.
            Defaults to None.

    Returns:
        dict: A nested dictionary where the keys are office types
            ("head_office" or "branches") and the values are lists
            of dictionaries with payroll details. Each dictionary contains:
              - pay_type (str): Type of the payroll category.
              - current_amount (float): Sum of payroll amounts for the current period.
              - comparison_amount (float): Sum of payroll amounts for the comparison
                period (or 0 if no comparison was provided).
              - difference (float): Difference between current and comparison period
                amounts.

    Raises:
        Any database-related exceptions or cursor initialization issues
        are not explicitly handled within the function.
    """
    params = [current_start, current_end]
    comparison_sql = ""
    has_comparison = compare_start and compare_end

    if has_comparison:
        params += [compare_start, compare_end]
        comparison_sql = """
            , SUM(CASE WHEN hrp.period BETWEEN %s AND %s THEN hrp.amount ELSE 0 END) AS comparison_amount
        """
    else:
        comparison_sql = ", 0 AS comparison_amount"

    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT
                CASE
                    WHEN company.is_main = TRUE THEN 'head_office'
                    ELSE 'branches'
                END AS office_type,
                pc.name AS pay_type,
                pc.id   AS pay_type_id,
                SUM(CASE WHEN hrp.period BETWEEN %s AND %s THEN hrp.amount ELSE 0 END) AS current_amount
                {comparison_sql}
            FROM hr_payroll hrp
            INNER JOIN hr_payrollsubcategory psc ON hrp.pay_type_id = psc.id
            INNER JOIN hr_payrollcategory pc ON psc.category_id = pc.id
            INNER JOIN company ON hrp.company_id = company.id
            GROUP BY office_type, pc.name, pc.id
            ORDER BY office_type, pc.name
        """, params)

        rows = cursor.fetchall()

    result = defaultdict(list)
    for office_type, pay_type, pc_id, current_amount, comparison_amount in rows:
        result[office_type].append({
            'pay_type': pay_type,
            'pay_type_id': pc_id,
            'current_amount': float(current_amount),
            'comparison_amount': float(comparison_amount),
            'difference': float(current_amount) - float(comparison_amount)
        })

    return dict(result)


class PayrollComparisonView(views.APIView):
    """
    Handles HTTP GET requests to provide payroll comparison summary between two date ranges.

    The PayrollComparisonView class processes and responds to API requests for payroll
    comparisons. Users must provide a start date and an end date for both the current
    and comparison periods in the query string parameters when making requests. The class
    leverages `get_comparison_summary` to retrieve summarized data for the given date ranges.

    Attributes:
        current_start: Defines the 'current_start' query parameter. It is a required
            parameter of string type and should be in 'YYYY-MM-DD' format.
        current_end: Defines the 'current_end' query parameter. It is a required parameter
            of string type and should be in 'YYYY-MM-DD' format.
        compare_start: Defines the 'compare_start' query parameter. It is a required
            parameter of string type and should be in 'YYYY-MM-DD' format.
        compare_end: Defines the 'compare_end' query parameter. It is a required parameter
            of string type and should be in 'YYYY-MM-DD' format.
        response: Specifies the response structure using
            PayrollSummaryResponseSerializer for successful requests.

    Methods:
        get(request, *args, **kwargs):
            Handles the HTTP GET request to retrieve the payroll comparison summary for the
            provided date ranges.
    """
    current_start = openapi.Parameter('current_start', openapi.IN_QUERY,
                                      description="Enter current start date in YYYY-MM-DD format",
                                      type=openapi.TYPE_STRING, required=True)
    current_end = openapi.Parameter('current_end', openapi.IN_QUERY,
                                    description="Enter current end date in YYYY-MM-DD format",
                                    type=openapi.TYPE_STRING, required=True)
    compare_start = openapi.Parameter('compare_start', openapi.IN_QUERY,
                                      description="Enter comparison start date in YYYY-MM-DD format",
                                      type=openapi.TYPE_STRING)
    compare_end = openapi.Parameter('compare_end', openapi.IN_QUERY,
                                    description="Enter comparison end date in YYYY-MM-DD format",
                                    type=openapi.TYPE_STRING)

    response = openapi.Response('response description', PayrollSummaryResponseSerializer)

    @swagger_auto_schema(manual_parameters=[current_start, current_end, compare_start, compare_end],
                         responses={200: response})
    def get(self, request, *args, **kwargs):
        current_start = self.request.GET.get('current_start')
        current_end = self.request.GET.get('current_end')
        compare_start = self.request.GET.get('compare_start')
        compare_end = self.request.GET.get('compare_end')
        summary = get_comparison_summary(current_start, current_end, compare_start, compare_end)
        return Response(summary)


def get_payroll_by_company_type(start_date, end_date, is_main=True):
    """
    Returns payroll totals grouped by department (if head office)
    or company name (if branch), along with pay categories.

    :param start_date: Start date of period
    :param end_date: End date of period
    :param is_main: True for Head Office, False for Branch
    :return: Dict[group_name] = [{category, total}]
    """
    query = """
            SELECT CASE
                       WHEN comp.is_main THEN d.name
                       ELSE comp.name
                       END       AS group_name,
                   c.name        AS category_name,
                   SUM(p.amount) AS total_amount
            FROM hr_payroll p
                     LEFT JOIN company_department d ON p.department_id = d.id
                     LEFT JOIN hr_payrollsubcategory s ON p.pay_type_id = s.id
                     LEFT JOIN hr_payrollcategory c ON s.category_id = c.id
                     LEFT JOIN company comp ON p.company_id = comp.id
            WHERE p.period BETWEEN %(start_date)s AND %(end_date)s
              AND comp.is_main = %(is_main)s
            GROUP BY group_name, c.name
            ORDER BY group_name, c.name
            """

    with connection.cursor() as cursor:
        cursor.execute(query, {
            'start_date': start_date,
            'end_date': end_date,
            'is_main': is_main
        })
        rows = cursor.fetchall()

    result = {}
    for group_name, category_name, total_amount in rows:
        group_name = group_name or 'Unknown'
        category_name = category_name or 'Unknown'
        result.setdefault(group_name, []).append({
            'category': category_name,
            'total': float(total_amount)
        })
    return result


class PayrollByDepartmentView(views.APIView):
    """
    Handles HTTP GET requests to provide payroll data grouped by department within a specified date range.

    The PayrollByDepartmentView class processes and responds to API requests for payroll data
    grouped by department. Users must provide a start date and an end date in the query string
    parameters when making requests. The class leverages `get_payroll_by_departments` to retrieve
    the payroll data for the given date range.

    Attributes:
        start_date: Defines the 'start_date' query parameter. It is a required
            parameter of string type and should be in 'YYYY-MM-DD' format.
        end_date: Defines the 'end_date' query parameter. It is a required parameter
            of string type and should be in 'YYYY-MM-DD' format.
        response: Specifies the response structure for successful requests.

    Methods:
        get(request, *args, **kwargs):
            Handles the HTTP GET request to retrieve the payroll data grouped by department for the provided date range.
    """
    start_date = openapi.Parameter('start_date', openapi.IN_QUERY,
                                   description="Enter start date in YYYY-MM-DD format",
                                   type=openapi.TYPE_STRING, required=True)
    end_date = openapi.Parameter('end_date', openapi.IN_QUERY,
                                 description="Enter end date in YYYY-MM-DD format",
                                 type=openapi.TYPE_STRING, required=True)
    is_main = openapi.Parameter('is_main', openapi.IN_QUERY,
                                description="Filter by company type: True for Head Office, False for Branch",
                                type=openapi.TYPE_BOOLEAN, required=False, default=True)

    @swagger_auto_schema(manual_parameters=[start_date, end_date, is_main],)
    def get(self, request, *args, **kwargs):
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        is_main = self.request.GET.get('is_main', 'true').lower() == 'true'
        summary = get_payroll_by_company_type(start_date, end_date, is_main)
        return Response(summary)

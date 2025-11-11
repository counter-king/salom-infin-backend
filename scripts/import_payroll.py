import sys

from apps.company.models import Department, Company
from apps.hr.models import Payroll, PayrollSubCategory
from utils.db_connection import oracle_connection, db_column_name

company_cache = {}
subcat_cache = {}


def get_dept_ids(code, company=None):
    try:
        # Prefetch parent and parent's parent in a single query
        department = (Department.objects
                      .select_related('parent', 'parent__parent')
                      .get(code=code, company_id=company.id))

        sub_sub_dept_id = department.id
        sub_dept_id = department.parent.id if department.parent else None
        top_level_dept_id = department.parent.parent.id if department.parent and department.parent.parent else (
                sub_dept_id or sub_sub_dept_id
        )

        return top_level_dept_id, sub_dept_id, sub_sub_dept_id

    except Department.MultipleObjectsReturned:
        print("[WARN] Multiple departments found for code:", code)
        return None, None, None

    except Department.DoesNotExist:
        print(f"[WARN] Department not found for code: {code}")
        try:
            print(f"[INFO] Attempting to find top level department for company: {company.name}")
            top_level = Department.objects.get(code=company.local_code, company_id=company.id)
            return top_level.id, None, None
        except Department.DoesNotExist:
            print(f"[WARN] Top level department not found for local_code: {company.local_code}")
            return None, None, None


def get_company_id(local_code):
    """Returns the company ID for a given code."""
    try:
        company = Company.objects.get(local_code=local_code)
        return company
    except Company.MultipleObjectsReturned:
        print(f"[WARN] Multiple companies found for local_code: {local_code}")
    except Company.DoesNotExist:
        print(f"[WARN] Company not found for local_code: {local_code}")
        return None


def get_payroll_sub_category_id(name):
    """Returns the payroll subcategory ID for a given name."""
    if name in subcat_cache:
        return subcat_cache[name]
    try:
        subcat = PayrollSubCategory.objects.get(name=name)
        subcat_cache[name] = subcat.id
        return subcat.id
    except PayrollSubCategory.DoesNotExist:
        print(f"[WARN] Subcategory not found for name: {name}")
        return None


def run(*args):
    conn = oracle_connection()
    cursor = conn.cursor()

    if not args:
        print("No date provided. Please provide a date in 'dd.mm.yyyy' format.")
        sys.exit(1)
    date_str = args[0]

    sql = """
          SELECT CASE
                     WHEN t.pay_id IN
                          (100, 102, 107, 108, 109, 110, 111, 112, 113, 115, 117, 118, 165, 200, 201, 207, 218, 220,
                           221, 222, 223, 227, 233) THEN 'Базовая заработная плата'
                     WHEN t.pay_id = 149 THEN 'Возмещение вреда в связи со смертью кормильца (сотрудника)'
                     WHEN t.pay_id = 153 THEN 'Выплата пенсионерам'
                     WHEN t.pay_id IN (146, 147) THEN 'Выплата по сокращению'
                     WHEN t.pay_id IN (145, 156, 184, 208, 230) THEN 'Выплата при увольнении'
                     WHEN t.pay_id = 199 THEN 'Выплаты членам совета банка'
                     WHEN t.pay_id IN (114, 202) THEN 'Годовая премия'
                     WHEN t.pay_id = 194 THEN 'Доплата за лекции в учебном центре'
                     WHEN t.pay_id IN (134, 163, 213) THEN 'Доплата к отпуску'
                     WHEN t.pay_id = 190 THEN 'Дополнительная оплата (профсоюз)'
                     WHEN t.pay_id IN (171, 197, 198, 237) THEN 'Командировочные'
                     WHEN t.pay_id IN (150, 151, 157, 192, 193) THEN 'Компенсационные выплаты'
                     WHEN t.pay_id IN (162, 170, 209, 212, 239) THEN 'Компенсация за неиспользованный отпуск'
                     WHEN t.pay_id = 144 THEN 'Компенсация на кормление ребенка'
                     WHEN t.pay_id IN (131, 132, 135, 136, 137, 138, 139, 148, 176, 191, 224, 225, 228, 231, 238)
                         THEN 'Материальная помощь'
                     WHEN t.pay_id IN (133, 235) THEN 'Материальная помощь с/х продукты'
                     WHEN t.pay_id IN (172, 242) THEN 'Оплата за время воен/службы'
                     WHEN t.pay_id IN (101, 105, 203) THEN 'Оплата за выходные и праздничные дни'
                     WHEN t.pay_id IN (174, 210) THEN 'Оплата за питание'
                     WHEN t.pay_id IN (103, 106, 226) THEN 'Оплата за сверхурочные работы'
                     WHEN t.pay_id IN (178, 236, 241) THEN 'Оплата по договору ГПХ'
                     WHEN t.pay_id IN (160, 161, 164, 205, 217) THEN 'Отпускные выплаты'
                     WHEN t.pay_id = 104 THEN 'Перечисление за субботник'
                     WHEN t.pay_id IN (141, 243) THEN 'Пособие по беременнности и родам'
                     WHEN t.pay_id IN (140, 155, 206) THEN 'Пособие по врем/нетрудоспособности'
                     WHEN t.pay_id IN (143, 154) THEN 'Пособие при рождении ребенка'
                     WHEN t.pay_id IN (142, 152, 216, 229, 232) THEN 'Пособия по уходу за ребенком'
                     WHEN t.pay_id IN (119, 120, 121, 123, 124, 125, 126, 127, 128, 130, 158, 159, 204, 215, 234)
                         THEN 'Премия за KPI'
                     WHEN t.pay_id IN (122, 211, 219) THEN 'Премия к праздничным датам'
                     WHEN t.pay_id = 195 THEN 'Прочие начисления'
                     WHEN t.pay_id = 129 THEN 'Разовая премия'
                     WHEN t.pay_id = 196 THEN 'Санаторно-курортное лечение (льгота)'
                     WHEN t.pay_id IN (116, 214) THEN 'Совмещение'
                     WHEN t.pay_id IN (173, 183) THEN 'Ценные подарки'
                     ELSE NULL
                     END                                AS Pay_type,
                 ibs.sl_util.Get_Emp_Dep_Code(t.emp_id) AS Dep,
                 t.filial,
                 t.branch_id,
                 t.period,
                 t.local_code,
                 SUM(t.Summ)                            AS Total
          FROM ibs.Sl_h_Calcs t
          WHERE t.Period = TO_DATE(:1, 'dd.mm.yyyy')
            AND t.is_loaded is null
            AND t.pay_id IN (
                             100, 102, 107, 108, 109, 110, 111, 112, 113, 115, 117, 118, 165, 200, 201, 207, 218, 220,
                             221, 222, 223, 227, 233,
                             149, 153, 146, 147, 145, 156, 184, 208, 230, 199, 114, 202, 194, 134, 163, 213, 190, 171,
                             197, 198, 237,
                             150, 151, 157, 192, 193, 162, 170, 209, 212, 239, 144,
                             131, 132, 135, 136, 137, 138, 139, 148, 176, 191, 224, 225, 228, 231, 238, 133, 235, 172,
                             242,
                             101, 105, 203, 174, 210, 103, 106, 226, 178, 236, 241, 160, 161, 164, 205, 217, 104,
                             141, 243, 140, 155, 206, 143, 154, 142, 152, 216, 229, 232,
                             119, 120, 121, 123, 124, 125, 126, 127, 128, 130, 158, 159, 204, 215, 234,
                             122, 211, 219, 195, 129, 196, 116, 214, 173, 183
              )
          GROUP BY CASE
                       WHEN t.pay_id IN
                            (100, 102, 107, 108, 109, 110, 111, 112, 113, 115, 117, 118, 165, 200, 201, 207, 218, 220,
                             221, 222, 223, 227, 233) THEN 'Базовая заработная плата'
                       WHEN t.pay_id = 149 THEN 'Возмещение вреда в связи со смертью кормильца (сотрудника)'
                       WHEN t.pay_id = 153 THEN 'Выплата пенсионерам'
                       WHEN t.pay_id IN (146, 147) THEN 'Выплата по сокращению'
                       WHEN t.pay_id IN (145, 156, 184, 208, 230) THEN 'Выплата при увольнении'
                       WHEN t.pay_id = 199 THEN 'Выплаты членам совета банка'
                       WHEN t.pay_id IN (114, 202) THEN 'Годовая премия'
                       WHEN t.pay_id = 194 THEN 'Доплата за лекции в учебном центре'
                       WHEN t.pay_id IN (134, 163, 213) THEN 'Доплата к отпуску'
                       WHEN t.pay_id = 190 THEN 'Дополнительная оплата (профсоюз)'
                       WHEN t.pay_id IN (171, 197, 198, 237) THEN 'Командировочные'
                       WHEN t.pay_id IN (150, 151, 157, 192, 193) THEN 'Компенсационные выплаты'
                       WHEN t.pay_id IN (162, 170, 209, 212, 239) THEN 'Компенсация за неиспользованный отпуск'
                       WHEN t.pay_id = 144 THEN 'Компенсация на кормление ребенка'
                       WHEN t.pay_id IN (131, 132, 135, 136, 137, 138, 139, 148, 176, 191, 224, 225, 228, 231, 238)
                           THEN 'Материальная помощь'
                       WHEN t.pay_id IN (133, 235) THEN 'Материальная помощь с/х продукты'
                       WHEN t.pay_id IN (172, 242) THEN 'Оплата за время воен/службы'
                       WHEN t.pay_id IN (101, 105, 203) THEN 'Оплата за выходные и праздничные дни'
                       WHEN t.pay_id IN (174, 210) THEN 'Оплата за питание'
                       WHEN t.pay_id IN (103, 106, 226) THEN 'Оплата за сверхурочные работы'
                       WHEN t.pay_id IN (178, 236, 241) THEN 'Оплата по договору ГПХ'
                       WHEN t.pay_id IN (160, 161, 164, 205, 217) THEN 'Отпускные выплаты'
                       WHEN t.pay_id = 104 THEN 'Перечисление за субботник'
                       WHEN t.pay_id IN (141, 243) THEN 'Пособие по беременнности и родам'
                       WHEN t.pay_id IN (140, 155, 206) THEN 'Пособие по врем/нетрудоспособности'
                       WHEN t.pay_id IN (143, 154) THEN 'Пособие при рождении ребенка'
                       WHEN t.pay_id IN (142, 152, 216, 229, 232) THEN 'Пособия по уходу за ребенком'
                       WHEN t.pay_id IN (119, 120, 121, 123, 124, 125, 126, 127, 128, 130, 158, 159, 204, 215, 234)
                           THEN 'Премия за KPI'
                       WHEN t.pay_id IN (122, 211, 219) THEN 'Премия к праздничным датам'
                       WHEN t.pay_id = 195 THEN 'Прочие начисления'
                       WHEN t.pay_id = 129 THEN 'Разовая премия'
                       WHEN t.pay_id = 196 THEN 'Санаторно-курортное лечение (льгота)'
                       WHEN t.pay_id IN (116, 214) THEN 'Совмещение'
                       WHEN t.pay_id IN (173, 183) THEN 'Ценные подарки'
                       ELSE NULL
                       END,
                   ibs.sl_util.Get_Emp_Dep_Code(t.emp_id),
                   t.filial,
                   t.branch_id,
                   t.period,
                   t.local_code \
          """

    cursor.execute(sql, (date_str,))
    rows = cursor.fetchall()
    field_map = db_column_name(cursor)
    count = 0
    payroll_objects = []

    for row in rows:
        company = get_company_id(row[field_map['LOCAL_CODE']])
        top_level_dept_id, sub_dept_id, sub_sub_dept_id = get_dept_ids(row[field_map['DEP']], company)
        pay_type_id = get_payroll_sub_category_id(row[field_map['PAY_TYPE']])
        # date_obj = datetime.strptime(row[field_map['PERIOD']], '%d/%m/%Y').date()

        if not all([company.id, pay_type_id]):
            continue  # skip if any reference is missing

        payroll = Payroll(
            company_id=company.id,
            period=row[field_map['PERIOD']],
            pay_type_id=pay_type_id,
            amount=row[field_map['TOTAL']],
            department_id=top_level_dept_id,
            sub_department_id=sub_dept_id,
            division_id=sub_sub_dept_id
        )
        payroll_objects.append(payroll)
        count += 1

    # Bulk create payroll objects to optimize database operations
    Payroll.objects.bulk_create(payroll_objects)

    cursor.close()
    conn.close()
    print('Payroll count ', count)

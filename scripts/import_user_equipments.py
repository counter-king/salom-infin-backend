from utils.db_connection import oracle_connection, db_column_name
from apps.user.models import User, UserEquipment


def run():
    """
    This script imports current active positions
    """

    conn = oracle_connection()
    cursor = conn.cursor()

    user_count = 0
    users = User.objects.filter(table_number__isnull=False)

    for user in users:
        sql = "select distinct (k.card_id), k.name, k.date_oper_beg, k.inv_num, Aa_Util.Get_Qr_Text(k.Card_Num,k.Name,k.Place_Id,k.Responsible_Id,k.Filial) qrText, j.name  from ibs.stg_s_mat_responsible j, ibs.aa_cards k  where k.pr_last_record = 1 and k.responsible_id = j.tab_num and k.state_id in (2, 66) and k.responsible_id =:1"
        cursor.execute(sql, (user.table_number,))

        cur = cursor.fetchall()

        if cur:
            for row in cur:
                user_equipment = UserEquipment(
                    user=user,
                    card_id=row[0],
                    name=row[1],
                    date_oper=row[2],
                    inv_num=row[3],
                    qr_text=row[4],
                    responsible=row[5]
                )
                user_equipment.save()
                user_count += 1

    print(f"User equipments imported: {user_count}")
    cursor.close()
    conn.close()

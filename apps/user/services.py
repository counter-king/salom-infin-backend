import uuid
from typing import Optional, Set, Dict, Literal, Iterable, Sequence

from apps.company.models import Department
from apps.user.models import (
    User,
    UserStatus,
    TopSigner,
    SignerModel,
)
from utils.constant_ids import user_search_status_ids
from utils.constants import CONSTANTS
from utils.tools import send_sms_to_phone

# Map of encoded strings to their corresponding characters
ENCODED_CHARS_MAP = {
    '&#1178;': 'Қ',
    '&#1179;': 'қ',
    '&#1202;': 'Ҳ',
    '&#1203;': 'ҳ',
    '&#1170;': 'Ғ',
    '&#1171;': 'ғ'
}


def send_otp_user(phone, code, otp_type, app_signature=''):
    if otp_type == CONSTANTS.OTP_TYPES.FOR_REGISTRATION:
        text = f"Salom CBU portalida roʻyxatdan oʻtishni tasdiqlash kodi: {code}. Kodni hech kimga bermang. {app_signature}"
    else:
        text = f"Salom CBU portalida parolni tiklash kodi: {code}. Kodni hech kimga bermang. {app_signature}"
    res = send_sms_to_phone(phone, text)

    return res


def format_date(date):
    if date:
        return date.strftime('%Y-%m-%d')
    else:
        return None


def get_condition_id(condition):
    return UserStatus.objects.get(code=condition).id


def get_department_id(department_code, company_id):
    try:
        return Department.objects.get(code=department_code, company_id=company_id).id
    except Department.DoesNotExist:
        return None


def get_top_level_department_id(department_code, company_id):
    try:
        department = Department.objects.get(code=department_code, company_id=company_id)
        if department.parent:
            return get_top_level_department_id(department.parent.code, company_id)
        else:
            return department.id
    except Department.DoesNotExist:
        return None


def get_dept_ids(code, company_id=None):
    try:
        # Prefetch parent and parent's parent in a single query
        department = (Department.objects
                      .select_related('parent', 'parent__parent')
                      .get(code=code, company_id=company_id))

        sub_sub_dept_id = department.id
        sub_dept_id = department.parent.id if department.parent else None
        top_level_dept_id = department.parent.parent.id if department.parent and department.parent.parent else (
                sub_dept_id or sub_sub_dept_id
        )

        return top_level_dept_id, sub_sub_dept_id
    except Department.DoesNotExist:
        return None, None


def replace_encoded_chars(text):
    for encoded, char in ENCODED_CHARS_MAP.items():
        text = text.replace(encoded, char)
    return text


def update_and_count(obj, field_name, user_count):
    original_value = getattr(obj, field_name, '')
    if original_value:
        updated_value = replace_encoded_chars(original_value)
        if updated_value != original_value:
            setattr(obj, field_name, updated_value)
            obj.save()
            user_count += 1
    return user_count


def make_inactive_signers(user_id):
    # Make disable top signer and signer
    # if he/she resigns or is fired

    try:
        signer = TopSigner.objects.get(user_id=user_id)
        signer.is_active = False
        signer.save()
    except TopSigner.DoesNotExist:
        pass

    try:
        signer = SignerModel.objects.get(user_id=user_id)
        signer.is_active = False
        signer.save()
    except SignerModel.DoesNotExist:
        pass


def normalize_phone(phone):
    if phone is None:
        return None

    if len(phone) <= 4:
        return f'{phone[0]}{phone[1]}-{phone[2]}{phone[3]}'


def normalize_login(login):
    if login:
        return login.split('@')[0]
    return None


def parse_vacation_row(row):
    return {
        'emp_id': row[0],
        'start_date': row[1],
        'end_date': row[2],
    }


def parse_sick_leave_row(row):
    return {
        'emp_id': row[0],
        'start_date': row[5],
        'end_date': row[6],
        'experience': row[2],
        'sick_leave_type': row[1],
        'sick_leave_coefficient': row[4],
    }


def parse_trip_row(row):
    return {
        'emp_id': row[0],
        'start_date': row[1],
        'end_date': row[2],
        'trip_address': row[3],
        'trip_reason': row[4],
    }


def _normalize_phone(raw) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, tuple):
        raw = raw[0] if raw else None
        if raw is None:
            return None
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("(") and s.endswith(")"):
            return s[1:-1].split(",", 1)[0].strip()
        return s
    return str(raw)


def _unique_username(base: Optional[str], used: Set[str], fallback: str) -> str:
    root = base or fallback
    if root not in used:
        used.add(root)
        return root
    while True:
        cand = f"{root}_{uuid.uuid4()}"
        if cand not in used:
            used.add(cand)
            return cand


def smart_title(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    return name[0].upper() + name[1:]


def existing_users_by_emp(
        emp_ids: Set[int],
        mode: Literal["status", "active"] = "status",
        *,
        status_ids: Optional[Iterable[int]] = None,
        fields: Optional[Sequence[str]] = None,
        values: Optional[Sequence[str]] = None,
        chunk_size: int = 1000,
) -> Dict[int, "User"]:
    """
    Return at most one canonical User per iabs_emp_id.

    Selection precedence (for duplicates with the same iabs_emp_id):
      - prefer is_user_active=True
      - then highest pk (newest)

    Args:
        emp_ids: set of employee IDs to fetch.
        mode: "status" → filter by status_id__in (active statuses),
              "active" → filter by is_user_active=True.
        status_ids: optional list of status_ids for "status" mode.
                    If None and mode="status", user_search_status_ids() will be called.
        fields: optional iterable for .only(...). If None, fetches full model.
        chunk_size: iterator chunk size for large querysets.

    Returns:
        Dict[int, User]: mapping iabs_emp_id → canonical User.
    """
    if not emp_ids:
        return {}

    # Base queryset per mode (no DB hit yet)
    if mode == "active":
        qs = User.objects.filter(iabs_emp_id__in=emp_ids, is_user_active=True)
    else:
        status_ids = list(status_ids) if status_ids is not None else list(user_search_status_ids())
        if not status_ids:
            return {}
        qs = User.objects.filter(iabs_emp_id__in=emp_ids, status_id__in=status_ids)

    # Portable path for other DBs: iterate once, keep first per key after ordering
    qs = qs.order_by("iabs_emp_id", "-is_user_active", "-id")
    if fields:
        qs = qs.only(*fields)
    if values:
        qs = qs.values(*values)

    out: Dict[int, User] = {}
    for u in qs.iterator(chunk_size=chunk_size):
        if u.iabs_emp_id not in out:
            out[u.iabs_emp_id] = u
    return out


def existing_usernames(phones: Set[str]) -> Set[str]:
    if not phones:
        return set()
    return set(User.objects.filter(username__in=phones).values_list("username", flat=True))

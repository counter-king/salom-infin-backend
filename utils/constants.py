from django.utils.translation import gettext_lazy as _

COLORS = (
    "#f44336", "#E91E63", "#9C27B0", "#673AB7", "#3F51B5",
    "#2196F3", "#03A9F4", "#00BCD4", "#009688", "#4CAF50",
    "#8BC34A", "#CDDC39", "#FFC107", "#FF9800", "#FF5722",
    "#795548"
)


class CONSTANTS:
    class USER_STATUSES:
        CONDITIONS = ('A', 'AP', 'OD', 'OF', 'I', 'OU', 'AO', 'OT', 'OS', 'OB', 'K', 'B', 'AS', 'AK', 'AT', 'KA')
        STRICT_CONDITIONS = ('A', 'AO', 'AB', 'OS', 'AS', 'AK', 'AT', 'OT', 'K', 'OB')

    class DOC_TYPE_ID:
        NOTICE = 1
        TRIP_NOTICE = 2
        TRIP_NOTICE_V2 = 35
        EXTEND_TRIP_NOTICE_V2 = 37
        EXTEND_TRIP_DECREE_V2 = 38
        BUSINESS_TRIP_NOTICE_FOREIGN = 40
        BUSINESS_TRIP_DECREE_FOREIGN = 41
        EXPLANATION_LETTER = 39
        SIMPLE_NOTICE = 9
        SERVICE_LETTER = 3
        APPLICATION = 5
        HR_ORDER = 2
        BUSINESS_TRIP_ORDER = 4
        LOCAL_BUSINESS_TRIP_ORDER = 29
        DECREE_TYPE = 4
        TRIP_DECREE_SUB_TYPE = 10
        LOCAL_DECREE_SUB_TYPE = 28
        TRIP_DECREE_V2 = 36
        NOTICE_FOR_ACCEPTANCE = 30
        ORDER_FOR_ACCEPTANCE = 31
        LEGAL_SERVICES = 8
        POA_FOR_LEGAL_SERVICES = 32
        POA_ACTING_FILIAL_MANAGER = 33
        POA_DEPUTY_FILIAL_MANAGER = 34
        POA_SECOND_TYPE_BSC_MANAGER = 42
        POA_DEPUTY_FILIAL_MANAGER_RETAIL = 43
        POA_BSO_MANAGER = 44
        POA_BSO_DEPUTY_MANAGER_BUSINESS = 45
        POA_BSO_DEPUTY_MANAGER_RETAIL = 46
        POA_BSO_CLIENT_MANAGER = 47
        POA_ELECTRON_DIGITAL_SIGNATURE = 48
        POA_OPERATIVE_GROUP_HEAD = 49
        POA_EMPLOYER_REPRESENTATIVE = 50
        POA_RETURN_ENFORCEMENT_DOCUMENT = 51
        POA_MEDIATION_AGREEMENT = 52
        POA_BSC_CLIENT_MANAGER = 53
        POA_BSC_ELECTRON_DIGITAL_SIGNATURE = 54
        POA_EMPLOYER_REPRESENTATIVE_CHAIRMAN_DEPUTIES = 55
        POA_EMPLOYER_REPRESENTATIVE_FIRST = 56
        POA_EMPLOYER_REPRESENTATIVE_GENERAL = 57
        POA_EMPLOYER_REPRESENTATIVE_SECOND = 58
        ACT_SERVICE_CONTRACT_WORKS = 59

        EXCLUDED_IDS = [
            APPLICATION
        ]

        NOTICES = [SIMPLE_NOTICE, NOTICE_FOR_ACCEPTANCE]

    class STATUSES:
        class GROUPS:
            TODO = "TODO"
            IN_PROGRESS = "IN_PROGRESS"
            DONE = "DONE"

            DEFAULT = None
            CHOICES = (
                (TODO, _("TO DO")),
                (IN_PROGRESS, _("IN PROGRESS")),
                (DONE, _("DONE")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

    class CORRESPONDENTS:
        class TYPES:
            PHYSICAL = "physical"
            LEGAL = "legal"
            ENTREPRENEUR = "entrepreneur"

            DEFAULT = None
            CHOICES = (
                (PHYSICAL, _("PHYSICAL")),
                (LEGAL, _("LEGAL")),
                (ENTREPRENEUR, _("ENTREPRENEUR")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

    class CHAT:
        class TYPES:
            GROUP = "group"
            PRIVATE = "private"

            DEFAULT = None
            CHOICES = (
                (GROUP, _("Group")),
                (PRIVATE, _("Private")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class ROLES:
            OWNER = "owner"
            ADMIN = "admin"
            MEMBER = "member"

            DEFAULT = MEMBER
            CHOICES = (
                (OWNER, _("Owner")),
                (ADMIN, _("Admin")),
                (MEMBER, _("Member")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class MESSAGE_TYPES:
            TEXT = "text"
            FILE = "file"
            IMAGE = "image"
            VIDEO = "video"
            AUDIO = "audio"
            LINK = "link"
            VOICE = "voice"

            DEFAULT = TEXT
            CHOICES = (
                (TEXT, _("Text")),
                (FILE, _("File")),
                (IMAGE, _("Image")),
                (VIDEO, _("Video")),
                (AUDIO, _("Audio")),
                (LINK, _("Link")),
                (VOICE, _("Voice")),
            )

            FILES = (
                FILE,
                IMAGE,
                VIDEO,
                AUDIO,
                LINK,
                VOICE,
            )

    class NOTIFICATION:
        class TYPES:
            APPROVE = "approve"
            REVIEW = "review"
            SIGN = "sign"
            ASSIGNMENT = "assignment"

            DEFAULT = None

            CHOICES = (
                (APPROVE, _("Approve")),
                (REVIEW, _("Review")),
                (SIGN, _("Sign")),
                (ASSIGNMENT, _("Assignment")),
            )

            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

            LIST = [APPROVE, REVIEW, SIGN, ASSIGNMENT]

    class QUERY_TYPES:
        EMPLOYEE_EXPERIENCE = "employee_experience"
        BY_GENDER = "by_gender"
        BY_CONDITION = "by_condition"
        BY_AGES = "by_ages"
        BY_RANK = "by_rank"
        BY_POSITION_RANK = "by_position_rank"
        COUNT_STAFF = "count_staff"
        COUNT_EMPS = "count_emps"
        COUNT_STAVKA = "count_stavka"
        COUNT_VACANT = "count_vacant"

        DEFAULT = None

        CHOICES = (
            (EMPLOYEE_EXPERIENCE, _("Employee experience")),
            (BY_GENDER, _("Group By Gender")),
            (BY_CONDITION, _("Group By Condition")),
            (BY_AGES, _("Group By Ages")),
            (BY_RANK, _("Group By Rank")),
            (BY_POSITION_RANK, _("Group By Position Rank")),
            (COUNT_STAFF, _("Group By Count Staff")),
            (COUNT_EMPS, _("Group By Count Emps")),
            (COUNT_STAVKA, _("Group By Count Stavka")),
            (COUNT_VACANT, _("Group By Count Vacant")),
        )

    class GENDER:
        MALE = "m"
        FEMALE = "f"

        DEFAULT = None
        CHOICES = (
            (MALE, _("male")),
            (FEMALE, _("female")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class CALENDAR_TYPES:
        EVENT = "event"
        TASK = "task"

        DEFAULT = None
        CHOICES = (
            (EVENT, _("event")),
            (TASK, _("task")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class CALENDAR_STATUS:
        PENDING = "pending"
        COMPLETED = "completed"
        CANCELED = "canceled"

        DEFAULT = PENDING
        CHOICES = (
            (PENDING, _("pending")),
            (COMPLETED, _("completed")),
            (CANCELED, _("canceled")),
        )

        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class CALENDAR_MEETING_SOURCE:
        ZOOM = "zoom"
        CISCO = "cisco"

        DEFAULT = None
        CHOICES = (
            (ZOOM, _("zoom")),
            (CISCO, _("cisco")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class NOTIFY_BY:
        SYSTEM = "system"
        EMAIL = "email"
        SMS = "sms"

        DEFAULT = None
        CHOICES = (
            (SYSTEM, _("system")),
            (EMAIL, _("email")),
            (SMS, _("sms")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class ACTIONS:
        CREATED = "created"
        UPDATED = "updated"
        DELETED = "deleted"

        DEFAULT = None
        CHOICES = (
            (CREATED, _("Created")),
            (UPDATED, _("Updated")),
            (DELETED, _("Deleted")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class COMPOSE:
        class IABS_ACTIONS:
            SENT = "sent"
            FAILED = "failed"
            CREATE = "create"
            PROLONG = "prolong"
            CANCEL = "cancel"

            DEFAULT = CREATE

            CHOICES = (
                (SENT, _("Sent")),
                (FAILED, _("Failed")),
                (CREATE, _("Create")),
                (PROLONG, _("Prolong")),
                (CANCEL, _("Cancel")),
            )

        class IABS_ACTION_TYPES:
            ORDER = "order"
            TRIP = "trip"
            TRIP_EXTEND = "trip_extend"
            TRIP_CANCEL = "trip_cancel"
            TRIP_PROLONG = "trip_prolong"

            DEFAULT = ORDER
            CHOICES = (
                (ORDER, _("Order")),
                (TRIP, _("Trip")),
                (TRIP_EXTEND, _("Trip Extend")),
                (TRIP_CANCEL, _("Trip Cancel")),
                (TRIP_PROLONG, _("Trip Prolong")),
            )

        class RECEIVERS:
            DEPARTMENTS = "departments"
            ORGANIZATIONS = "organizations"
            COMPANIES = "companies"

            DEFAULT = None
            CHOICES = (
                (DEPARTMENTS, _("Departments")),
                (ORGANIZATIONS, _("Organizations")),
                (COMPANIES, _("Companies")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class LINK_TYPES:
            IS_CHILD_OF = "is_child_of"
            IS_PARENT_OF = "is_parent_of"
            IS_RELATED_TO = "is_related_to"

            DEFAULT = IS_RELATED_TO
            CHOICES = (
                (IS_CHILD_OF, _("Is child of")),
                (IS_PARENT_OF, _("Is parent of")),
                (IS_RELATED_TO, _("Is related to")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class SIGNER_TYPES:
            BASIC_SIGNER = "basic_signer"
            SIGNER = "signer"
            INVITED = "invited"
            NEGOTIATOR = "negotiator"

            DEFAULT = SIGNER
            CHOICES = (
                (BASIC_SIGNER, _("Basic signer")),
                (SIGNER, _("Signer")),
                (INVITED, _("Invited")),
                (NEGOTIATOR, _("Negotiator")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class TRIP_TYPE:
            LOCAL = "local"
            FOREIGN = "foreign"
            CHANGED_LOCAL = "changed_local"
            CHANGED_FOREIGN = "changed_foreign"

            DEFAULT = LOCAL
            CHOICES = (
                (LOCAL, _("Local")),
                (FOREIGN, _("Foreign")),
                (CHANGED_LOCAL, _("Changed local")),
                (CHANGED_FOREIGN, _("Changed foreign")),
            )

        class TRIP_ROUTE:
            BY_CAR = "by_car"
            BY_TRAIN = "by_train"
            BY_PLANE = "by_plane"
            BY_BUS = "by_bus"
            BY_SERVICE_CAR = "by_service_car"

            DEFAULT = BY_CAR
            CHOICES = (
                (BY_CAR, _("By car")),
                (BY_TRAIN, _("By train")),
                (BY_PLANE, _("By plane")),
                (BY_BUS, _("By bus")),
                (BY_SERVICE_CAR, _("By service car")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }
            GET_TRANSPORT = {
                BY_CAR: 'Yo‘lovchi avtomobili (taksi)',
                BY_TRAIN: 'Temir yo‘l transporti',
                BY_PLANE: 'Havo transporti',
                BY_BUS: 'Avtobus',
                BY_SERVICE_CAR: 'Bankning xizmat avtomobili'
            }

        class BOOKING_TYPE:
            ONE_WAY = "one_way"
            ROUND_TRIP = "round_trip"
            MULTI_CITY = "multi_city"

            DEFAULT = ONE_WAY
            CHOICES = (
                (ONE_WAY, _("One way")),
                (ROUND_TRIP, _("Round trip")),
                (MULTI_CITY, _("Multi city")),
            )
            GET_ROUTE = {
                ONE_WAY: "Bir tomonli",
                ROUND_TRIP: "Borish qaytish",
                MULTI_CITY: "Ko'p shaharli"
            }

        class BOOKING_CLASS:
            ECONOMY = "economy"
            BUSINESS = "business"
            FIRST = "first"
            SLEEPER = "sleeper"
            SEAT = "seat"

            DEFAULT = None
            CHOICES = (
                (ECONOMY, _("Economy")),
                (BUSINESS, _("Business")),
                (FIRST, _("First")),
                (SLEEPER, _("Sleeper")),
                (SEAT, _("Seat")),
            )

            GET_SEGMENT_CLASS = {
                ECONOMY: "Ekonom",
                BUSINESS: "Biznes",
                FIRST: "Birinchi",
                SLEEPER: "Yotoq",
                SEAT: "O'rindosh"
            }

        class DESTINATION_TYPES:
            BRANCH = "branch"
            REGION = "region"
            DEFAULT = REGION

            CHOICES = (
                (BRANCH, _("Branch")),
                (REGION, _("Region")),
            )

    class REQUEST_METHODS:
        GET = "GET"
        POST = "POST"
        PUT = "PUT"
        DELETE = "DELETE"
        HEAD = "HEAD"
        OPTIONS = "OPTIONS"
        PATCH = "PATCH"

        DEFAULT = None
        CHOICES = (
            (GET, _("GET")),
            (POST, _("POST")),
            (PUT, _("PUT")),
            (DELETE, _("DELETE")),
            (HEAD, _("HEAD")),
            (OPTIONS, _("OPTIONS")),
            (PATCH, _("PATCH")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class SIGNATURE:
        class SIGN_ON:
            WEB = "web"
            MOBILE = "mobile"

            DEFAULT = WEB
            CHOICES = (
                (WEB, _("Web")),
                (MOBILE, _("Mobile")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

    class BIRTHDAY_REACTIONS:
        PARTY_POPPER = "party_popper"
        CAKE = "cake"
        GIFT_BOX = "gift_box"
        CHAMPAGNE = "champagne"

        DEFAULT = None

        CHOICES = (
            (PARTY_POPPER, _("Party popper")),
            (CAKE, _("Cake")),
            (GIFT_BOX, _("Gift box")),
            (CHAMPAGNE, _("Champagne")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

        LIST = [
            PARTY_POPPER,
            CAKE,
            GIFT_BOX,
            CHAMPAGNE
        ]

    class MOOD_REACTIONS:
        VERY_HAPPY = "very_happy"
        HAPPY = "happy"
        NEUTRAL = "neutral"
        UNHAAPPY = "unhappy"
        VERY_UNHAPPY = "very_unhappy"

        DEFAULT = None
        CHOICES = (
            (VERY_HAPPY, _("Very happy")),
            (HAPPY, _("Happy")),
            (NEUTRAL, _("Neutral")),
            (UNHAAPPY, _("Unhappy")),
            (VERY_UNHAPPY, _("Very unhappy")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

        LIST = [
            VERY_HAPPY,
            HAPPY,
            NEUTRAL,
            UNHAAPPY,
            VERY_UNHAPPY
        ]

    class NEWS_CONTENT_TYPE:
        TEXT = "text"
        IMAGE = "image"
        VIDEO = "video"
        AUDIO = "audio"
        QUOTE = "quote"

        DEFAULT = TEXT
        CHOICES = (
            (TEXT, _("Text")),
            (IMAGE, _("Image")),
            (VIDEO, _("Video")),
            (AUDIO, _("Audio")),
            (QUOTE, _("Quote")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class NEWS_STATUS:
        DRAFT = "draft"
        PENDING = "pending"
        PUBLISHED = "published"
        ARCHIVED = "archived"
        DECLINED = "declined"

        DEFAULT = DRAFT
        CHOICES = (
            (DRAFT, _("Draft")),
            (PENDING, _("Pending")),
            (PUBLISHED, _("Published")),
            (ARCHIVED, _("Archived")),
            (DECLINED, _("Declined")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

        PENDING_LIST = [DRAFT, DECLINED]
        LIST = [
            PUBLISHED,
            DECLINED
        ]

    class NEWS_LIKE_EMOJI:
        LIKE = "like"
        LOVE = "love"
        HAHA = "haha"
        WOW = "wow"
        SAD = "sad"
        ANGRY = "angry"

        DEFAULT = None
        CHOICES = (
            (LIKE, _("Like")),
            (LOVE, _("Love")),
            (HAHA, _("Haha")),
            (WOW, _("Wow")),
            (SAD, _("Sad")),
            (ANGRY, _("Angry")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

        LIST = [
            LIKE,
            LOVE,
            HAHA,
            WOW,
            SAD,
            ANGRY,
            DEFAULT
        ]

    class APP_TYPES:
        ANDROID = "android"
        IOS = "ios"
        DESKTOP = "desktop"
        CHAT_ANDROID = "chat_android"
        CHAT_IOS = "chat_ios"

        DEFAULT = None
        CHOICES = (
            (ANDROID, _("Android")),
            (IOS, _("IOS")),
            (DESKTOP, _("Desktop")),
            (CHAT_ANDROID, _("Chat Android")),
            (CHAT_IOS, _("Chat IOS")),
        )
        AS_RESPONSE = {
            'choices': [{"name": y, "code": x} for x, y in CHOICES],
            'default': DEFAULT
        }

    class OTP_TYPES:
        FORGET_PASSWORD = "forget_password"
        FOR_REGISTRATION = "for_registration"

    class ATTENDANCE:
        class PAYROLL_STATUS:
            DRAFT = "draft"
            IN_REVIEW = "in_review"
            APPROVED = "approved"
            REJECTED = "rejected"
            FROZEN = "frozen"

            DEFAULT = DRAFT
            CHOICES = (
                (DRAFT, _("Draft")),
                (IN_REVIEW, _("In review")),
                (APPROVED, _("Approved")),
                (REJECTED, _("Rejected")),
                (FROZEN, _("Frozen (locked)")),
            )

        class USER_TYPES:
            MANAGER = "manager"
            HR = "hr"
            DEFAULT = None

            CHOICES = (
                (MANAGER, _("Manager")),
                (HR, _("HR")),
            )

        class TYPES:
            CHECKIN = "IN"
            CHECKOUT = "OUT"

            DEFAULT = CHECKIN
            CHOICES = (
                (CHECKIN, _("Check In")),
                (CHECKOUT, _("Check Out")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class EXCEPTION_KIND:
            LATE = "late"
            ABSENT = "absent"
            EARLY_LEAVE = "early_leave"
            MISSED_CHECKIN = "missed_checkin"
            MISSED_CHECKOUT = "missed_checkout"

            DEFAULT = None
            CHOICES = (
                (LATE, _("Late")),
                (ABSENT, _("Absent")),
                (EARLY_LEAVE, _("Early leave")),
                (MISSED_CHECKIN, _("Missed check-in")),
                (MISSED_CHECKOUT, _("Missed check-out")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class EXCEPTION_STATUS:
            PENDING = "pending"
            APPROVED = "approved"
            REJECTED = "rejected"

            DEFAULT = PENDING
            CHOICES = (
                (PENDING, _("Pending")),
                (APPROVED, _("Approved")),
                (REJECTED, _("Rejected")),
            )
            AS_RESPONSE = {
                'choices': [{"name": y, "code": x} for x, y in CHOICES],
                'default': DEFAULT
            }

        class CHECK_IN_STATUS:
            ON_TIME = "came-on-time"
            REASONABLE = "excused"
            NOT_CHECKED = "no-entry-marked"
            WAS_LATE = "late-arrival"
            ABSENT = "not-came"

            CHOICES = (
                (ON_TIME, _("Vaqtida keldi")),
                (REASONABLE, _("Sababli")),
                (NOT_CHECKED, _("Kirish qayd etilmagan")),
                (WAS_LATE, _("Kechikdi")),
                (ABSENT, _("Kelmadi")),
            )

        class CHECK_OUT_STATUS:
            EARLY_LEAVE = "early-departure"
            ON_TIME_LEAVE = "normal-exit"
            NOT_CHECKED = "no-exit-marked"
            ABSENT = "not-came"
            REASONABLE = "excused"

            CHOICES = (
                (EARLY_LEAVE, _("Erta ketdi")),
                (REASONABLE, _("Sababli")),
                (ON_TIME_LEAVE, _("Vaqtida ketdi")),
                (NOT_CHECKED, _("Chiqish qayd etilmagan")),
                (ABSENT, _("Kelmadi")),
            )

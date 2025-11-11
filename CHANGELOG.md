# CHANGELOG

<!-- version list -->

## v1.0.0 (2025-11-11)

- Initial Release

## v1.38.1 (2025-11-08)

### Performance Improvements

- Remove unused HR helper functions and refactor payroll views
  ([`230bade`](https://github.com/goaziz/digital-workspace/commit/230bade75b505745eeb88ea11f743522b1114fb9))


## v1.38.0 (2025-11-08)

### Features

- Reintroduce `department` to payroll filters and serializers
  ([`05721e8`](https://github.com/goaziz/digital-workspace/commit/05721e85c2f78d9910f70084402ea188df117a76))


## v1.37.0 (2025-11-08)

### Chores

- Update changelog with details on `PayrollPeriod` mid/final approval enhancements
  ([`b06f516`](https://github.com/goaziz/digital-workspace/commit/b06f516814e20e74e6043083834b1a94c39cb08a))

### Features

- Enhance `PayrollPeriod` admin filters with locking and type fields
  ([`15f9b48`](https://github.com/goaziz/digital-workspace/commit/15f9b48c10359e02dd8c7b7c2f8ff52ab821bf21))


## v1.36.0 (2025-11-08)

### Chores

- Update changelog to include detailed notes on `PayrollPeriod` enhancements
  ([`37c91a6`](https://github.com/goaziz/digital-workspace/commit/37c91a657ad96af1e49b2e1ca1e61031621385c1))

### Features

- Add mid/final approval windows to `PayrollPeriod` and update approval process
  ([`f0d92a2`](https://github.com/goaziz/digital-workspace/commit/f0d92a2dbe8f4d88384918c20af7a287f061c61e))
  - Add `mid_locked`, `final_locked`, `mid_approved_at`, and `final_approved_at` fields to `PayrollPeriod` model.
  - Update serializers to validate and handle `window` parameter for approvals.
  - Enhance approval logic to support `mid` and `final` windows with status updates and locking mechanisms.
  - Refactor payroll generator to account for locked windows when processing periods.
  - Include migration for new fields and adjustments.


## v1.35.0 (2025-11-08)

### Chores

- Update changelog to reflect `valid_to` renamed to `valid_until` across HR models and views
  ([`5888630`](https://github.com/goaziz/digital-workspace/commit/58886309ff6ec135920b91701472dea0010a239c))

### Features

- Reintroduce `department` to `PayrollPeriod` with updated logic and admin enhancements
  ([`ae5ea39`](https://github.com/goaziz/digital-workspace/commit/ae5ea391c67ac719dcd82b09976240b9ddd73861))
  - Add `department` and `type` fields to `PayrollPeriod` for distinguishing between department and branch periods.
  - Update `_ensure_period_for` to support `department` and `type` parameters.
  - Modify admin interface to include `department` in `autocomplete_fields` and enhance display logic with `get_name`.
  - Adjust serializers to reflect the reintroduction of `department` and include new `name` field for periods.
  - Add migration to enforce new `unique_together` constraints on `PayrollPeriod`.


## v1.34.0 (2025-11-08)

### Features
- Rename `valid_to` to `valid_until` across HR models and views ([`899793f`](https://github.com/goaziz/digital-workspace/commit/899793f731e12ebd4add46ddfe3b49db6c3e506f))

  - Update all HR model fields, serializers, and admin configurations to reflect the new naming.
  - Refactor related querysets, views, and helpers for consistency.
  - Add migration to handle the field renaming in models.


## v1.33.2 (2025-11-08)


## v1.33.1 (2025-11-08)

### Performance Improvements

- Remove `department` field from `PayrollPeriod` and update related logic
  ([`ab611f5`](https://github.com/goaziz/digital-workspace/commit/ab611f548573f7b9a1a3f190870588466b69f9d1))

### Refactoring

- Streamline excluded employees caching in payroll generator
  ([`39896fc`](https://github.com/goaziz/digital-workspace/commit/39896fc5584e302ae1945b7f47422c4fb9d68144))


## v1.33.0 (2025-11-08)

### Features

- Add payroll approval process and refine payroll handling
  ([`adf79b2`](https://github.com/goaziz/digital-workspace/commit/adf79b23f651ca69d4f263bba0cba1fc655f9040))


## v1.32.0 (2025-11-07)

### Features

- Hik personList api made verify to false
  ([`d600cc9`](https://github.com/goaziz/digital-workspace/commit/d600cc943e6236127d6ecb07cd2ce14b7b858333))


## v1.31.1 (2025-11-07)

### Bug Fixes

- Correct `mark_outage` call to use today's reason in daily attendance sync
  ([`ee1603e`](https://github.com/goaziz/digital-workspace/commit/ee1603e90adaa0b8e12a93087df8dcac150323af))


## v1.31.0 (2025-11-07)

### Chores

- Update changelog to include `status` addition in `hr_user` extra fields
  ([`08fd335`](https://github.com/goaziz/digital-workspace/commit/08fd335636b1616833f6ddac3431b5c1b6cb4671))

### Features

- Enhance outage handling in daily attendance sync and add reason tracking
  ([`08d60c2`](https://github.com/goaziz/digital-workspace/commit/08d60c2adb49ad8da63e4c1bc03aed6a65719141))

### Performance Improvements

- Set default HIK_BASE_URL and clean up error handling in face_client
  ([`6ae4382`](https://github.com/goaziz/digital-workspace/commit/6ae4382056b5251d61c3e131c68a2d2d16da60c8))


## v1.30.0 (2025-11-06)

### Features

- Include `status` in `hr_user` extra fields for attendance serializer
([`b9129c2`](https://github.com/goaziz/digital-workspace/commit/b9129c202cf5d4a48b4c47c5f99edcbd668f92bc))

## v1.29.1 (2025-11-06)

### Performance Improvements

- Optimize `sync_daily_attendance` by switching to async task execution
  ([`3d7dc53`](https://github.com/goaziz/digital-workspace/commit/3d7dc53b8a6f865bbe6a0125d9c358783a42fb45))

## v1.29.0 (2025-11-05)

### Features

- Department filter change
  ([`21b5b70`](https://github.com/goaziz/digital-workspace/commit/21b5b70cd7b90f029b3037f129cf72f7f70d6ea8))

## v1.28.0 (2025-11-05)

### Chores

- Update changelog with detailed payroll and attendance enhancements
  ([`f97f97c`](https://github.com/goaziz/digital-workspace/commit/f97f97c33b8bea4a5dd6f140982bcb94b572fd4b))

### Features

- Add DepartmentManagerFilter for enhanced filtering in DepartmentManagerView
  ([`3a375d6`](https://github.com/goaziz/digital-workspace/commit/3a375d66a0d9732f63b7f891b4520f01540fe61e))

## v1.27.0 (2025-11-05)

### Features

- Enhance payroll processing and exception handling
  ([`5198b90`](https://github.com/goaziz/digital-workspace/commit/5198b90a925a2a732191fdccdaa86922190a873d))
    - Add `PayrollPeriodListSerializer` for improved list view representation.
    - Update payroll views with dynamic serializer selection, filtering, and search capabilities.
    - Introduce `get_excluded_employees` for caching excluded employee IDs in payroll calculations.
    - Refactor payroll cell upsertion to include exception handling and approved letters.
    - Expand `PayrollCell.kind` choices for better category representation (e.g., vacation, sick).
    - Add new migrations for `AttendanceException`, `DailySummary`, and `PayrollCell` field updates.

- Update attendance status handling and refactor constants usage
  ([`faf6264`](https://github.com/goaziz/digital-workspace/commit/faf62640db0a73f5c4f06c5e49ca76eb0aa81023))
    - Set main object's status to 'approved' or 'rejected' during approval processing.
    - Replace direct constant calls with `ATTENDANCE` shorthand for readability.
    - Add `explanation_letter` field to `AttendanceException` for better exception tracking.

### Performance Improvements

- Rename `send_user_confirmation` to `send_user_status` for clarity and update related calls
  ([`882d5c7`](https://github.com/goaziz/digital-workspace/commit/882d5c78e0ec2c28bd0d3f62c036729eeae67676))
    - Replace method name in `TelegramClient` to improve readability.
    - Add denial notification on user unlinking for consistency in status updates.

## v1.26.0 (2025-11-05)

### Chores

- Comment out conditional checks in notification task logic
  ([`12d4089`](https://github.com/goaziz/digital-workspace/commit/12d408949805e6bc9d97e49f8c82eb68e4b346e4))

- Remove 'is_active' from readonly fields in Notification admin
  ([`db900a7`](https://github.com/goaziz/digital-workspace/commit/db900a74c520c5b5233981927efa884b6ab5fa84))

### Features

- Activation and deactivation comments added to Exception Employee model
  ([`ca90ade`](https://github.com/goaziz/digital-workspace/commit/ca90ade89b990aeac9d0f37a2c7255489057bb36))

## v1.25.0 (2025-11-04)

### Features

- Add payroll views for subtotal and grid calculations
  ([`70c3e91`](https://github.com/goaziz/digital-workspace/commit/70c3e91d03f7451686a9bf18a3a5228fcf0d2af3))

## v1.24.2 (2025-11-04)

### Performance Improvements

- Add `self` parameter to `send_telegram_notification` task signature for task instance access
  ([`9d167f4`](https://github.com/goaziz/digital-workspace/commit/9d167f424a7af4b2e7902dc6d2122a4e1b232e4b))

## v1.24.1 (2025-11-04)

### Chores

- Update changelog for v1.24.0 with payroll management details
  ([`f0444dd`](https://github.com/goaziz/digital-workspace/commit/f0444ddc14eb5cdfe8c23c224a78f894daf04245))

### Performance Improvements

- Update Telegram notification response and refactor payload
  ([`25099db`](https://github.com/goaziz/digital-workspace/commit/25099db13a3215e9e032f1e69ae019fd41350a91))

## v1.24.0 (2025-11-04)

### Features

- Add `PayrollPeriod`, `PayrollRow`, `PayrollCell`, and `PayrollApproval` models with necessary fields and indices for
  payroll handling.
- Create serializers and views to manage payroll data and workflows.
- Implement payroll generation services with support for mid and final pay dates, working days, and automated task
  scheduling.
- Introduce Django admin configurations for payroll components.
- Replace telegram notification logic with Celery task for async processing.
- Update related modules and constants for payroll integration.

## v1.23.0 (2025-11-04)

### Features

- Lunch start and end time fields added to Work Schedule model. Some error messages added
  ([`544433e`](https://github.com/goaziz/digital-workspace/commit/544433e27dbb33ee45f149703635d1fe31d34138))

## v1.22.0 (2025-11-04)

### Features

- Enhance notification rendering logic and attendance syncing
  ([`f9b01c4`](https://github.com/goaziz/digital-workspace/commit/f9b01c4ffecca451e9f3d39395b1e030a30908e2))
    - Add `_SafeMap` for safer context handling in notification rendering.
    - Introduce support for Python `str.format` style templates.
    - Implement `sync_attendance_backfill_then_today` for improved backfill and reconciliation in attendance sync.
    - Add `IngestState` model for tracking sync progress and outages.
    - Register `IngestState` in admin with filters and date hierarchy.
    - Add `/send-test-message/` API for sending test Telegram notifications.
    - Refactor Telegram client to support batch payloads with per-item result handling.
    - Improve `send_telegram_notification` task with batch processing and retry logic.

## v1.21.0 (2025-11-01)

### Features

- Exception employees CRUD operation and logic
  ([`a4ef0fe`](https://github.com/goaziz/digital-workspace/commit/a4ef0fe3bec741e13e805f4fd00a0dba985d028e))

- Exception employees CRUD operation and logic
  ([`8ad12a0`](https://github.com/goaziz/digital-workspace/commit/8ad12a097892ef8fdbc75311bbe149af16dad7c2))

## v1.20.0 (2025-10-31)

### Features

- Add validation for active Telegram profiles during pairing
  ([`f9da05b`](https://github.com/goaziz/digital-workspace/commit/f9da05b89bf9f51fbef4616d4542b6985c2b7542))

## v1.19.0 (2025-10-31)

### Features

- Introduce `transaction.atomic` to ensure data consistency during compose creation.
- Add `_log_create_action` for deferred activity logging after commit.
- Implement `_maybe_add_to_trip` to conditionally link compose and trip objects.
- Introduce `_handle_subtype_specifics` with support for custom logic per document subtype.
- Enhance readability and modularity by restructuring `create` method.

## v1.18.1 (2025-10-31)

### Bug Fixes

- Correct pairing TTL to match intended duration
  ([`be0a67d`](https://github.com/goaziz/digital-workspace/commit/be0a67d0392387dda7dbe63ffc98d85dfd800f8b))

## v1.18.0 (2025-10-31)

## v1.17.0 (2025-10-30)

### Chores

- Update CHANGELOG.md with recent Telegram client and error message changes
  ([`01be7a0`](https://github.com/goaziz/digital-workspace/commit/01be7a07555651fea6c0e896210f3ec5f8f05e41))

### Features

- Add Telegram profiles endpoint and improve admin functionality
  ([`427e914`](https://github.com/goaziz/digital-workspace/commit/427e9143db8b04606a1a9eef6ebb23b81d269ef4))

## v1.16.0 (2025-10-30)

### Features

- Add new error messages for manager deletion restrictions
- Introduce `TelegramClient.send_user_confirmation` to send pairing status updates to users.
- Update Telegram pairing approval logic to notify users upon approval or denial.
- Add a new endpoint `/send-user-confirmation` in Telegram client API.
- Update `send_message` method with improved URL handling.
  ([`6a1fa02`](https://github.com/goaziz/digital-workspace/commit/6a1fa0245c61a208f7bb9f03380d4466a6786d86))

## v1.15.0 (2025-10-30)

### Features

- Add unlink Telegram feature and improve manager syncing APIs
  ([`71dd16d`](https://github.com/goaziz/digital-workspace/commit/71dd16dd355370c7413ec80023e18288263a57cd))

- Add unlink Telegram feature and improve manager syncing APIs
  ([`e779f58`](https://github.com/goaziz/digital-workspace/commit/e779f58f97b58624a7d6fd54d881e025cf37dff1))

## v1.14.0 (2025-10-30)

### Chores

- Updated CHANGELOG.md with some definitions of last release
  ([`6dc798b`](https://github.com/goaziz/digital-workspace/commit/6dc798b2bf72b1fe80b6deb933780cc9cd2b2343))

### Features

- Enhance branch and department managers listing with optimized queries
  ([`ed6181e`](https://github.com/goaziz/digital-workspace/commit/ed6181e9898f523b71ab9868aa8940ef83301031))

## v1.13.0 (2025-10-29)

### Features

- Replace JWT tokens with short hashed tokens for telegram pairing
  ([`4ef2000`](https://github.com/goaziz/digital-workspace/commit/4ef20005877691cf3a1b43ebaba31a7b6814ff6c))
    - Replace JWT-based pairing tokens with simple random alphanumeric tokens
    - Hash tokens before storing in database for security
    - Add generate_short_token() and hash_token() utility functions
    - Update TelegramPairRequest creation and validation to use hashed tokens
    - Add ordering by created_at (descending) to TelegramPairRequest admin
    - Reduce pairing TTL from 300 to 100 seconds

## v1.12.2 (2025-10-29)

### Performance Improvements

- Add AttendanceException filter and increase pairing TTL
  ([`7ee69ec`](https://github.com/goaziz/digital-workspace/commit/7ee69ec82e9cf39094e3daf527074df7d25b5dc7))

## v1.12.1 (2025-10-29)

## v1.12.0 (2025-10-29)

### Chores

- Fix duplicate entry for v1.10.0 in CHANGELOG
  ([`527a87b`](https://github.com/goaziz/digital-workspace/commit/527a87b9090eb8a7b717067e6eea6e62e684bc22))

- Update CHANGELOG with Telegram pairing system details
  ([`5a86f68`](https://github.com/goaziz/digital-workspace/commit/5a86f680543f67bec4d024126ba304ebe8082ced))

### Features

- Additional_data field added to compose model
  ([`bd4eede`](https://github.com/goaziz/digital-workspace/commit/bd4eede4b85502c6783a891cece34fe7418ae7b4))

- Additional_data field added to compose model
  ([`9140ca6`](https://github.com/goaziz/digital-workspace/commit/9140ca6b5e653d0cf0083b98ce9418a1227e79d6))

## v1.11.0 (2025-10-28)

### Chores

- Update CHANGELOG with details for Telegram notifications and attendance approval refactor
  ([`48e6c72`](https://github.com/goaziz/digital-workspace/commit/48e6c72bd2fa79d7d052afa2cd5d631cd54025eb))

### Features

- Implement Telegram pairing system with models, views, and APIs
  ([`a53c4ce`](https://github.com/goaziz/digital-workspace/commit/a53c4ce5359d37fd561ca1f726b319a6d05404ae))
    - Added `TelegramPairRequest` model for managing Telegram pairing requests.
    - Implemented API endpoints for requesting, confirming, and handling Telegram pairing via deep links and bot
      callbacks.
    - Included migrations for new models and schema changes, including a new `telegram_phone` field.
    - Integrated Django admin for managing `TelegramPairRequest` objects.
    - Added utility functions for pairing token generation and validation.
    - Updated `private_urls.py` to include notification-related routes.

## v1.10.0 (2025-10-28)

### Chores

- Update CHANGELOG with BranchManager and DepartmentManager details
  ([`67dd4a4`](https://github.com/goaziz/digital-workspace/commit/67dd4a4a05dace25a939485b86a4c51d56319e8f))

### Features

- Add Telegram notification system with models, tasks, and client
  ([`5b766fd`](https://github.com/goaziz/digital-workspace/commit/5b766fdf71832ac00887626aa55ddc890bca3a20))
    - Implemented `TelegramClient` for message sending, signature generation, and handling retries.
    - Introduced models for `TelegramProfile`, `NotificationTemplate`, and `TelegramNotificationLog` with necessary
      fields and constraints.
    - Added admin integrations for managing Telegram-related models.
    - Created Celery task for robust notification handling, including retry logic and idempotency.
    - Setup migrations to include new models in the database schema.
    - Integrated caching of notification templates for performance optimization.

- Refactor attendance exception approval system
  ([`93bc46a`](https://github.com/goaziz/digital-workspace/commit/93bc46ac1381490342ea678c0895148523a3f11f))
    - Introduced `AttendanceExceptionApproval` model to manage approvals for exceptions.
    - Removed `decided_by`, `decided_at`, and `decision_note` fields from `AttendanceException` model.
    - Updated serializers to handle approvals and introduced `AttendanceExceptionApprovalSerializer`.
    - Modified admin views to include inline approvals using `AttendanceExceptionApprovalInline`.
    - Updated querysets in attendance views to prefetch `approvals` for optimized retrieval.
    - Introduced Celery task `create_attendance_exc_approval` for routing approvals to managers based on organizational
      hierarchy.
    - Added migrations for schema changes and new fields like `manager` in `AttendanceException`.
    - Simplified approval/reject actions by removing direct decision update fields from the model.
    - Enhanced constants for user types and approvals in `CONSTANTS.ATTENDANCE`.

## v1.9.0 (2025-10-28)

### Features

- Add BranchManager and DepartmentManager models with admin views and APIs
- Introduced `BranchManager` and `DepartmentManager` models with constraints and indexing for efficient querying.
- Added admin configurations for `BranchManager` and `DepartmentManager` for management in the admin panel.
- Created dedicated viewsets and serializers to support CRUD operations and custom actions (activate, deactivate,
  reorder, move up/down, set primary).
- Registered new routes for manager APIs in the router.
- Added migration scripts to modify database schema accordingly.
  ([`e8d0b2b`](https://github.com/goaziz/digital-workspace/commit/e8d0b2b84329f18bd405c1e0a236e5d9b26a8814))

## v1.8.1 (2025-10-27)

### Performance Improvements

- Add filterset fields to AttendanceViewSet
  ([`438122d`](https://github.com/goaziz/digital-workspace/commit/438122ded6c226d6dc0ec5351e255e280993d542))

## v1.8.0 (2025-10-27)

### Chores

- Fix formatting for imports in attendance views
  ([`6d0008a`](https://github.com/goaziz/digital-workspace/commit/6d0008a3f474272ba253123560bb5c065fdae944))

### Features

- Prefetch attendance exceptions and add violation details in serializer
  ([`4ee3228`](https://github.com/goaziz/digital-workspace/commit/4ee32281378ec400814fe4ffc456d56f11969f27))

### Performance Improvements

- Consolidate and relocate `start_date` and `end_date` parameter definitions in AttendanceView
  ([`7bce415`](https://github.com/goaziz/digital-workspace/commit/7bce415bc671d240054e2b1ed9bdf6a25848f9e5))

## v1.7.0 (2025-10-27)

### Chores

- Update CHANGELOG with bulk creation and employee field updates for AttendanceException
  ([`526bba0`](https://github.com/goaziz/digital-workspace/commit/526bba06fbb2248508773ab989578c3fdf1f248f))

### Features

- Add `clear_scopes` action to AssignedHrUsersView
  ([`52dedbc`](https://github.com/goaziz/digital-workspace/commit/52dedbc14ecc1f9fbb001697e95fcf0eabc9d84a))

## v1.6.1 (2025-10-27)

### Performance Improvements

- Add bulk creation for AttendanceException and update employee field behavior
- Add `create` method to support bulk creation of `AttendanceException` records.
- Update `employee` field in `AttendanceException` model to allow `null` values and use `SET_NULL` for on-delete
  behavior.
- Include migration script to reflect changes in the database schema.
  ([`89f89ed`](https://github.com/goaziz/digital-workspace/commit/89f89ed0fdc4d982929d8d881cc210efc5d5cec7))

## v1.6.0 (2025-10-27)

### Chores

- Temporarily disable pytest step in server CI workflow
  ([`8083b60`](https://github.com/goaziz/digital-workspace/commit/8083b60b061f61db65518f91d8263b6509dd97e9))

### Features

- Enhance attendance summary calculation and add calendar seeding command
  ([`00d3947`](https://github.com/goaziz/digital-workspace/commit/00d3947ffd79a647a103d0d8839fed4d6e507717))

## v1.5.0 (2025-10-26)

### Bug Fixes

- Uploading a file bug fixed if the filename is non-ASCII, serving file improved
  ([`11e47a9`](https://github.com/goaziz/digital-workspace/commit/11e47a9756ede2efa12729ee26b7fb7ef230b663))

### Chores

- Update CHANGELOG with AttendanceException feature details
  ([`05f8ac4`](https://github.com/goaziz/digital-workspace/commit/05f8ac4e5343d45256f6bb97c1ec4b577792d641))

### Features

- Add language support for birthday users caching
  ([`695f3cf`](https://github.com/goaziz/digital-workspace/commit/695f3cf91b18bfd0ec5ef404290d1d80eab9af28))

## v1.4.0 (2025-10-24)

### Chores

- Update CHANGELOG for v1.3.0 with new features and adjustments
  ([`b490e6e`](https://github.com/goaziz/digital-workspace/commit/b490e6e47cb0330a3a3c2d5a7859abfae3312d98))

### Features

- Add AttendanceException model, serializers, views, and API endpoints
- Introduce `AttendanceException` model with related fields, choices, and associations.
- Add `AttendanceExceptionSerializer` for data validation and serialization.
- Implement `AttendanceExceptionViewSet` with actions for approval and rejection.
- Register `attendance-exceptions` endpoint in attendance URLs.
- Add migrations for `AttendanceException` model and related changes.
- Update admin interface for managing attendance exceptions.
  ([`058469a`](https://github.com/goaziz/digital-workspace/commit/058469abbc7a6f676226dba6c84962267966ff9e))

## v1.3.0 (2025-10-24)

- Add duration and peaks fields to File model, along with updates to views and serializers.
- Integrate peaks and duration into ChatMessageFile model temporarily; subsequently removed for scope adjustment.
- Update consumers for enriched files_payload handling, including new field data.
- Adjust admin interface to display message type for ChatMessageFile.
- Introduce EmployeeScheduleFilter with multiple filtering options (e.g., employee, department, date range).
- Replace filterset_fields with filterset_class in EmployeeScheduleViewSet.
- Update imports and minor formatting adjustments in attendance views.
- Introduce AssignedHrUsersView to list users with HR scopes (branch or department) with optional scope_type filters (
  branch, department, or both).
- Add ScopedUserSerializer to serialize scoped user data.
- Register hr/assigned-users endpoint in attendance URLs.
- Update relevant imports in serializers and views.

## v1.2.0 (2025-10-23)

### Features

- Add attendance summary endpoint for the current user and date range parameters
  ([`d1eed87`](https://github.com/goaziz/digital-workspace/commit/d1eed8778d7edb0a0f91ff60a1ae978c29487780))

- Add HRBranchScope and HRDepartmentScope models with API endpoints, serializers, admin integration,
  and migrations
  ([`8a5d94f`](https://github.com/goaziz/digital-workspace/commit/8a5d94fc1ed129f2b35822b885e9cba4166a7ea4))

## v1.1.0 (2025-10-22)

## v1.0.1 (2025-10-21)

### Chores

- Remove CHANGELOG.md and refine release workflow branch targets
  ([`4ae22bd`](https://github.com/goaziz/digital-workspace/commit/4ae22bd2bbbeb1e30d1a31e582625f5c734c70d6))

- Remove outdated semantic-release instructions from config
  ([`9c0cad7`](https://github.com/goaziz/digital-workspace/commit/9c0cad7284a9d50676bad2cb789c2a583ccfe666))

- Update release workflow to configure git identity and clarify comments
  ([`3ba5799`](https://github.com/goaziz/digital-workspace/commit/3ba5799725b141245e35a5a9b11e407b956e000e))

- Update release workflow to use GH_BOT_TOKEN for semantic-release
  ([`c093164`](https://github.com/goaziz/digital-workspace/commit/c093164c1b069e1ebdba2054f458fbb131afa6f1))

### Performance Improvements

- Optimize message delivery with bulk insert; add personalized policy endpoints and JSON utility
  ([`08aef75`](https://github.com/goaziz/digital-workspace/commit/08aef753fd85e0b3d082bb94fd6398f3d8fb979b))

## v1.0.0 (2025-10-20)

### Chores

- Bump project version to 1.0.0 in pyproject.toml
  ([`0a41885`](https://github.com/goaziz/digital-workspace/commit/0a4188557720b18fa9ec42e2bca5445e42663f10))

- Update semantic release configuration and workflows; rename workflow, adjust branches, and improve
  versioning settings
  ([`c9e8176`](https://github.com/goaziz/digital-workspace/commit/c9e8176e34276d6af89bccf9a1e6c9ab9c0df0b9))

## v0.0.0 (2025-10-20)

- Initial Release

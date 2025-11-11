from django.urls import path, include
from graphene_django.views import GraphQLView
from rest_framework.routers import DefaultRouter

from apps.reference import views
from apps.reference.graphql.schema import schema

router = DefaultRouter()
router.register(r'comments', views.CommentViewSet, basename='comments')
router.register(r'status', views.StatusModelViewSet, basename='status')
router.register(r'correspondents', views.CorrespondentViewSet, basename='correspondents')
router.register(r'employee-groups', views.EmployeeGroupViewSet, basename='employee-groups')
router.register(r'short-descriptions', views.ShortDescriptionViewSet, basename='short-descriptions')
router.register(r'activity-logs', views.ActionModelViewSet, basename='activity-logs')
router.register(r'journals', views.JournalViewSet, basename='journals')
router.register(r'document-types', views.DocumentTypeViewSet, basename='document-types')
router.register(r'document-sub-types', views.DocumentSubTypeViewSet, basename='document-sub-types')
router.register(r'countries', views.CountryViewSet, basename='countries')
router.register(r'regions', views.RegionViewSet, basename='regions')
router.register(r'city-distances', views.CityDistanceViewSet, basename='city-distance')
router.register(r'districts', views.DistrictViewSet, basename='districts')
router.register(r'languages', views.LanguageModelViewSet, basename='languages')
router.register(r'delivery-types', views.DeliveryTypeViewSet, basename='delivery-types')
router.register(r'priorities', views.PriorityViewSet, basename='priorities')
router.register(r'document-titles', views.DocumentTitleViewSet, basename='document-titles')
router.register(r'expense-types', views.ExpenseTypeViewSet, basename='expense-types')
router.register(r'app-versions', views.AppVersionViewSet, basename='app-version')
router.register(r'attendance-reasons', views.AttendanceReasonViewSet, basename='attendance-reasons')
router.register(r'exception-employees', views.ExceptionEmployeeViewSet, basename='exception-employees')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('reference/graphql/', GraphQLView.as_view(graphiql=True, schema=schema), name='graphql'),
]

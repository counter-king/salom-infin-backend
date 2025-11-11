from django.urls import path, include
from graphene_django.views import GraphQLView
from rest_framework.routers import DefaultRouter

from apps.docflow import views
from apps.docflow.graphql.schema import schema

router = DefaultRouter()
router.register(r'docflow/(?P<company>[\w-]+)', views.DocFlowViewSet, basename='docflow')
router.register(r'for-review/(?P<company>[\w-]+)', views.ReviewerViewSet, basename='for-review')
router.register(r'resolution/(?P<company>[\w-]+)', views.ResolutionViewSet, basename='resolution')
router.register(r'my-resolution/(?P<company>[\w-]+)', views.MyResolutionViewSet, basename='my-resolution')
router.register(r'my-assignment/(?P<company>[\w-]+)', views.MyAssignmentViewSet, basename='my-assignment')
router.register(r'my-controls/(?P<company>[\w-]+)', views.MyControlViewSet, basename='my-controls')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/document-statistics/departments/',
         views.DepartmentStatistics.as_view(),
         name='document-statistics-departments'
         ),
    path('docflow/graphql/', GraphQLView.as_view(graphiql=True, schema=schema), name='docflow-graphql'),

]

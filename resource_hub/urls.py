from django.urls import path
from . import views

urlpatterns = [
    path('', views.resource_hub, name='resource_hub'),
    path('browse/', views.browse_resources, name='browse_resources'),
    path('resource/<int:pk>/', views.resource_detail, name='resource_detail'),
    path('resource/<int:pk>/bookmark/', views.toggle_bookmark, name='toggle_bookmark'),
    path('resource/<int:pk>/progress/', views.update_progress, name='update_progress'),
    path('my-learning/', views.my_learning, name='my_learning'),
]
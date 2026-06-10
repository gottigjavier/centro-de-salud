"""URL configuration for the reports module."""
from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_dashboard, name="dashboard"),
    path("profesionales/", views.widget_profesionales, name="widget_profesionales"),
    path("cancelaciones/", views.widget_cancelaciones, name="widget_cancelaciones"),
    path("recursos/", views.widget_recursos, name="widget_recursos"),
    path("tendencia/", views.widget_tendencia, name="widget_tendencia"),
    path("frecuentes/", views.widget_frecuentes, name="widget_frecuentes"),
    path("horas-pico/", views.widget_horas_pico, name="widget_horas_pico"),
    path("csv/profesionales/", views.csv_profesionales, name="csv_profesionales"),
    path("csv/cancelaciones/", views.csv_cancelaciones, name="csv_cancelaciones"),
    path("csv/recursos/", views.csv_recursos, name="csv_recursos"),
    path("csv/tendencia/", views.csv_tendencia, name="csv_tendencia"),
    path("csv/frecuentes/", views.csv_frecuentes, name="csv_frecuentes"),
    path("csv/horas-pico/", views.csv_horas_pico, name="csv_horas_pico"),
]

from django.urls import path

from .views import ByCategoryReportView, CashflowReportView

urlpatterns = [
    path("reports/cashflow/", CashflowReportView.as_view(), name="report-cashflow"),
    path("reports/by-category/", ByCategoryReportView.as_view(), name="report-by-category"),
]

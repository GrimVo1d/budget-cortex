from django.urls import path

from .views import CashflowReportView

urlpatterns = [
    path("reports/cashflow/", CashflowReportView.as_view(), name="report-cashflow"),
]

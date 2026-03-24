from __future__ import annotations

from django.db import models


class FxRate(models.Model):
    """Snapshot rate ``1 base = rate * quote`` effective on the given date.

    ``rate`` is `numeric(20,10)` — wide enough for ten-decimal precision
    that some weak-currency pairs need without losing accuracy.
    """

    base = models.CharField(max_length=3)
    quote = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=10)
    effective_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["base", "quote", "effective_on"],
                name="fx_rate_unique_per_day",
            ),
        ]
        indexes = [
            models.Index(fields=["base", "quote", "-effective_on"], name="fx_rate_lookup_idx"),
        ]
        ordering = ["-effective_on"]

    def __str__(self) -> str:
        return f"{self.base}/{self.quote}={self.rate} on {self.effective_on:%Y-%m-%d}"

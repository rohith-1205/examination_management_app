from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


def update_slot_status(slot):
    booked_seats = sum(
        booking.status in ("Booked", "Completed") for booking in slot.bookings
    )
    slot.available_seats = max(slot.capacity - booked_seats, 0)

    if slot.status not in ("Cancelled", "Completed"):
        if slot.available_seats == 0:
            slot.status = "Full"
        else:
            slot.status = "Available"

    return slot


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to access that page.", "warning")
                return redirect(url_for("auth.login"))

            if current_user.role != role:
                flash("You do not have permission to access that page.", "danger")
                endpoint = f"{current_user.role}.dashboard"
                return redirect(url_for(endpoint))

            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator

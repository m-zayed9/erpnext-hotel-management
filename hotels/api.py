from datetime import datetime, timedelta
import frappe
from frappe import _
from frappe.utils import getdate,flt
from collections import defaultdict
import json
from frappe.utils import nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils import flt, nowdate
from frappe.utils import nowdate
from frappe.model.naming import make_autoname


@frappe.whitelist(allow_guest=False)
def add_payment_to_sales_invoice(invoice_name, paid_amount, payment_mode, paid_date=None, reference_no=None, reference_date=None):
    try:
        if not invoice_name or not paid_amount:
            frappe.throw("Invoice name and paid amount required")
        
        paid_amount = flt(paid_amount)
        paid_date = getdate(paid_date or nowdate())
        reference_date = getdate(reference_date or paid_date)
        
        # Validate sales invoice
        sales_invoice = frappe.get_doc("Sales Invoice", invoice_name)
        if sales_invoice.docstatus != 1:
            frappe.throw("Sales Invoice must be submitted")
        
        # Validate payment mode exists
        if not frappe.db.exists("Mode of Payment", payment_mode):
            frappe.throw(f"Payment mode '{payment_mode}' does not exist")
        
        # Create payment entry using the standard function
        payment_entry = get_payment_entry(
            dt="Sales Invoice",
            dn=invoice_name,
            party_amount=paid_amount
        )
        
        # Set payment details
        payment_entry.posting_date = paid_date
        payment_entry.mode_of_payment = payment_mode
        payment_entry.paid_amount = paid_amount
        payment_entry.received_amount = paid_amount
        
        # Check if the payment mode is linked to a bank account
        paid_to_account_type = frappe.db.get_value("Account", payment_entry.paid_to, "account_type")
        if paid_to_account_type == "Bank":
            # If paying to a bank account, reference details are mandatory
            payment_entry.reference_no = reference_no or f"AUTO-{invoice_name}"
            payment_entry.reference_date = reference_date
        
        # Update the payment amount allocated to the invoice
        for ref in payment_entry.references:
            if ref.reference_doctype == "Sales Invoice" and ref.reference_name == invoice_name:
                ref.allocated_amount = paid_amount
                break
        
        # Save the payment entry first
        payment_entry.insert()
        
        # Submit the payment entry
        payment_entry.submit()
        
        # Commit the transaction - This is crucial!
        frappe.db.commit()
        
        return {
            "payment_entry": payment_entry.name,
            "status": "Success",
            "message": "Payment entry created and submitted successfully"
        }
        
    except Exception as e:
        # Rollback in case of error
        frappe.db.rollback()
        frappe.log_error(f"Error creating payment entry: {str(e)}")
        frappe.throw(f"Failed to create payment entry: {str(e)}")

@frappe.whitelist(allow_guest=True)
def search(checkin_date, checkout_date, adults, children, rooms):
    checkin_date = getdate(checkin_date)
    checkout_date = getdate(checkout_date)

    if checkin_date >= checkout_date:
        frappe.throw(_("Check-out date must be after check-in date."))

    # Fetch all room availability entries
    records = frappe.get_all(
        "Room Availability",
        filters={"date": ["between", [checkin_date, checkout_date]]},
        fields=[
            "room_id", "hotel_id", "price", "date",
            "available_rooms", "adults_per_room", "childs_per_room"
        ]
    )

    # Group by (room_id, hotel_id)
    grouped = defaultdict(list)
    for r in records:
        grouped[(r.room_id, r.hotel_id)].append(r)

    num_days = (checkout_date - checkin_date).days
    hotel_rooms = defaultdict(list)

    for (room_id, hotel_id), entries in grouped.items():
        if len(entries) != num_days:
            continue

        min_avail = min(e.available_rooms for e in entries)
        avg_price = sum(float(e.price) for e in entries) / num_days

        if (
            entries[0].adults_per_room < int(adults)
            or entries[0].childs_per_room < int(children)
            or min_avail < int(rooms)
        ):
            continue

        hotel_rooms[hotel_id].append({
            "room_id": room_id,
            "available_rooms": min_avail,
            "average_price": round(avg_price, 2),
            'currency': get_default_currency()
        })

    results = []
    for hotel_id, room_list in hotel_rooms.items():
        hotel_doc = frappe.get_doc("Hotel", hotel_id)
        hotel_data = {
            "name": hotel_doc.name,
            "description": hotel_doc.description,
            "city": hotel_doc.city,
            "chain_code": hotel_doc.chain_code,
            "rating": hotel_doc.rating,
            "latitude": hotel_doc.latitude,
            "longitude": hotel_doc.longitude,
            "images": [img.image for img in hotel_doc.images],
            "amenities": [a.amenity_id for a in hotel_doc.amenities],
            "currency": get_default_currency(),
        }

        lowest_avg_price = min(r["average_price"] for r in room_list)

        results.append({
            "hotel": hotel_data,
            "rooms": room_list,
            "lowest_avg_price": lowest_avg_price
        })

    return results


@frappe.whitelist(allow_guest=True)
def get_hotel_rooms(hotel_id, checkin_date, checkout_date, adults, children, rooms):
    """
    Get detailed information about rooms available in a specific hotel for the given dates and guest requirements.
    
    Args:
        hotel_id: The ID of the hotel to search
        checkin_date: Check-in date
        checkout_date: Check-out date
        adults: Number of adults per room
        childs: Number of children per room
        rooms: Number of rooms required
    
    Returns:
        Dictionary containing hotel details and available rooms with their complete information
    """
    # Validate dates
    checkin_date = getdate(checkin_date)
    checkout_date = getdate(checkout_date)
    if checkin_date >= checkout_date:
        frappe.throw(_("Check-out date must be after check-in date."))

    # Validate hotel exists
    if not frappe.db.exists("Hotel", hotel_id):
        frappe.throw(_("Hotel not found."))

    # Fetch hotel details
    hotel_doc = frappe.get_doc("Hotel", hotel_id)
    hotel_data = {
        "name": hotel_doc.name,
        "description": hotel_doc.description,
        "city": hotel_doc.city,
        "chain_code": hotel_doc.chain_code,
        "rating": hotel_doc.rating,
        "latitude": hotel_doc.latitude,
        "longitude": hotel_doc.longitude,
        "images": [img.image for img in hotel_doc.images],
        "amenities": [a.amenity_id for a in hotel_doc.amenities],
        "currency": get_default_currency()
    }

    # Fetch all room availability entries for this hotel
    records = frappe.get_all(
        "Room Availability",
        filters={
            "date": ["between", [checkin_date, checkout_date]],
            "hotel_id": hotel_id
        },
        fields=[
            "room_id", "price", "date", "available_rooms", 
            "adults_per_room", "childs_per_room"
        ]
    )

    # Group by room_id
    grouped = defaultdict(list)
    for r in records:
        grouped[r.room_id].append(r)

    num_days = (checkout_date - checkin_date).days + 1
    rooms_data = []

    for room_id, entries in grouped.items():
        # Skip if not available for the entire date range
        if len(entries) != num_days:
            continue

        # Check if room meets requirements
        min_avail = min(e.available_rooms for e in entries)
        avg_price = sum(float(e.price) for e in entries) / num_days

        if (
            entries[0].adults_per_room < int(adults)
            or entries[0].childs_per_room < int(children)
            or min_avail < int(rooms)
        ):
            continue

        # Get room details
        room_doc = frappe.get_doc("Room", room_id)

        # Get room type details
        room_type_doc = frappe.get_doc("Room Type", room_doc.room_type)

        # Prepare daily prices

        room_data = {
            "room_id": f"{room_id}|{checkin_date}|{checkout_date}|{adults}|{children}|{rooms}",
            "available_rooms": min_avail,
            "average_price": round(avg_price, 2),
            "currency": get_default_currency(),
            "images": [img.image for img in room_doc.images],
            "amenities": [a.amenity_id for a in room_doc.amenities],
            "room_type": {
                "name": room_type_doc.room_type_name,
                "description": room_type_doc.description,
                "board_type": room_type_doc.board_type,
                "beds": room_type_doc.beds,
                "max_adults": room_type_doc.max_adults,
                "max_childs": room_type_doc.max_childs,
            },
        }

        rooms_data.append(room_data)

    # Sort rooms by price (lowest first)
    rooms_data.sort(key=lambda x: x["average_price"])
    if rooms_data:
        hotel_data["lowest_avg_price"] = rooms_data[0]["average_price"]

    return {
        "hotel": hotel_data,
        "rooms": rooms_data
    }


@frappe.whitelist(allow_guest=True)
def get_room_details(room_id):

    room_id, checkin_date, checkout_date, adults, children, rooms = room_id.split("|")
    # Validate dates
    checkin_date = getdate(checkin_date)
    checkout_date = getdate(checkout_date)
    if checkin_date >= checkout_date:
        frappe.throw(_("Check-out date must be after check-in date."))

    # Validate hotel exists
    if not frappe.db.exists("Room", room_id):
        frappe.throw(_("Room not found."))

    # Fetch hotel details
    room_doc = frappe.get_doc("Room", room_id)
    hotel_doc = frappe.get_doc("Hotel", room_doc.hotel)
    hotel_data = {
        "name": hotel_doc.name,
        "description": hotel_doc.description,
        "city": hotel_doc.city,
        "chain_code": hotel_doc.chain_code,
        "rating": hotel_doc.rating,
        "latitude": hotel_doc.latitude,
        "longitude": hotel_doc.longitude,
        "images": [img.image for img in hotel_doc.images],
        "amenities": [a.amenity_id for a in hotel_doc.amenities],
    }

    # Fetch all room availability entries for this hotel
    records = frappe.get_all(
        "Room Availability",
        filters={
            "date": ["between", [checkin_date, checkout_date]],
            "room_id": room_id
        },
        fields=[
            "room_id", "price", "date", "available_rooms",
            "adults_per_room", "childs_per_room"
        ]
    )

    # Group by room_id
    grouped = defaultdict(list)
    for r in records:
        grouped[r.room_id].append(r)

    num_days = (checkout_date - checkin_date).days + 1
    rooms_data = []

    for room_id, entries in grouped.items():
        # Skip if not available for the entire date range
        if len(entries) != num_days:
            continue

        # Check if room meets requirements
        min_avail = min(e.available_rooms for e in entries)
        avg_price = sum(float(e.price) for e in entries) / num_days

        if (
            entries[0].adults_per_room < int(adults)
            or entries[0].childs_per_room < int(children)
            or min_avail < int(rooms)
        ):
            continue

        # Get room details
        room_doc = frappe.get_doc("Room", room_id)

        # Get room type details
        room_type_doc = frappe.get_doc("Room Type", room_doc.room_type)

        # Prepare daily prices

        room_data = {
            "room_id": f"{room_id}|{checkin_date}|{checkout_date}|{adults}|{children}|{rooms}",
            "available_rooms": min_avail,
            "average_price": round(avg_price, 2),
            "currency": get_default_currency(),
            "images": [img.image for img in room_doc.images],
            "amenities": [a.amenity_id for a in room_doc.amenities],
            "room_type": {
                "name": room_type_doc.room_type_name,
                "description": room_type_doc.description,
                "board_type": room_type_doc.board_type,
                "beds": room_type_doc.beds,
                "max_adults": room_type_doc.max_adults,
                "max_childs": room_type_doc.max_childs,
            },
        }

        rooms_data.append(room_data)

    return {
        "hotel": hotel_data,
        "room": rooms_data[0]
    }


@frappe.whitelist(allow_guest=False)
def create_booking(data):
    if isinstance(data, str):
        data = json.loads(data)

    total_price = 0
    booking_room_map = {}

    aggregated = defaultdict(lambda: {"quantity": 0})
    for room in data.get("booking_rooms", []):
        parts = room["room_id"].split("|")
        key = room["room_id"]

        if aggregated[key]["quantity"] == 0:
            aggregated[key].update(
                {
                    "room_id": parts[0],
                    "checkin_date": parts[1],
                    "checkout_date": parts[2],
                }
            )
        aggregated[key]["quantity"] += 1

    # Final result list
    result = list(aggregated.values())
    booking_room_map = []
    total_price = 0
    checkin_date = None
    checkout_date = None
    for room in result:

        checkin = datetime.strptime(room["checkin_date"], "%Y-%m-%d").date()
        checkout = datetime.strptime(room["checkout_date"], "%Y-%m-%d").date()
        checkin_date = checkin 
        checkout_date = checkout
        delta = (checkout - checkin).days

        for day_offset in range(delta):
            booking_date = checkin + timedelta(days=day_offset)
            room_price = frappe.get_value(
                "Room Availability",
                filters={ 
                    "room_id": room["room_id"],
                    "date": booking_date,
                },
                fieldname=[
                    "price",
                ],
            )
            booking_room_map.append(
                {
                    "room_id": room["room_id"],
                    "booking_date": booking_date,
                    "price": room_price,
                    "quantity": room["quantity"],
                }
            )

            total_price += room_price * room["quantity"]

    frappe.flags.ignore_permissions = True
    booking = frappe.get_doc(
        {
            "doctype": "Booking",
            "customer": ensure_customer_exists(data['customer']),
            "check_in_date": checkin_date,
            "check_out_date": checkout_date,
            "total_price": total_price,
            "booking_rooms": booking_room_map,
        }
    )
    booking.insert(ignore_permissions=True)
    # booking.submit()

    booking_dict = booking.as_dict()
    return {"status": "success", "booking": get_booking_details(booking_dict["name"])}


@frappe.whitelist(allow_guest=False)
def get_booking_details(booking_id):
    if not booking_id:
        frappe.throw(_("Booking ID is required"))

    booking = frappe.get_doc("Booking", booking_id)

    data = {
        "name": booking.name,
        "customer": booking.customer,
        "check_in_date": booking.check_in_date,
        "check_out_date": booking.check_out_date,
        "total_price": booking.total_price,
        "currency": get_default_currency(),
        "sales_invoice_id": booking.sales_invoice_id,
        "rooms": [],
    }

    for booking_room in booking.booking_rooms:
        room_doc = frappe.get_doc("Room", booking_room.room_id)
        data['hotel_id'] = room_doc.hotel
        # Get Room Type details
        room_type_data = None
        if room_doc.room_type:
            room_type_doc = frappe.get_doc("Room Type", room_doc.room_type)
            room_type_data = {
                "name": room_type_doc.name,
                "description": room_type_doc.description,
                "beds": room_type_doc.beds,
                "max_adults": room_type_doc.max_adults,
                "max_childs": room_type_doc.max_childs,
                "board_type": room_type_doc.board_type,
            }

        data["rooms"].append(
            {
                "room_id": room_doc.name,
                "booking_date": booking_room.booking_date,
                "price": booking_room.price,
                "quantity": booking_room.quantity,
                "hotel": room_doc.hotel,
                "item_id": room_doc.item_id,
                "room_type": room_type_data,
            }
        )
    return data


def get_default_currency():
    global_defaults = frappe.get_doc("Global Defaults", "Global Defaults")
    currency = global_defaults.default_currency
    return currency


def ensure_customer_exists(customer_name):

    # Check if a customer exists by customer_name
    existing_customer = frappe.get_value(
        "Customer", {"customer_name": customer_name}, "name"
    )

    if not existing_customer:
        new_customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": customer_name,
                "customer_type": "Individual",
            }
        ).insert(ignore_permissions=True)
        customer = new_customer.name
    else:
        customer = existing_customer  # Link to existing customer.name

    return customer_name


@frappe.whitelist(allow_guest=True)
def create_sales_invoice_from_reservation(data):
    try:
        payload = json.loads(data)
        reservation = payload.get("json_repr")
        hotel_bookings = reservation.get("hotelBookings", [])
        guests = reservation.get("guests", [])

        # --- Customer Name ---
        customer_name = (
            f"{guests[0]['firstName']} {guests[0]['lastName']}_{reservation['id']}"
            if guests
            else reservation["id"]
        )

        # --- Ensure Customer Exists ---
        if not frappe.db.exists("Customer", customer_name):
            customer = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "customer_type": "Individual",
                }
            )
            customer.flags.ignore_mandatory = True
            customer.insert(ignore_permissions=True)
        else:
            customer = customer_name

        # --- Create Invoice ---
        invoice = frappe.new_doc("Sales Invoice")
        invoice.customer = customer
        invoice.set_posting_time = 1
        # valid_date = get_valid_fiscal_date()
        invoice.posting_date = nowdate()
        invoice.due_date = nowdate()  # Assuming immediate payment

        room_groups = defaultdict(
            lambda: {
                "qty": 0,
                "rate": 0,
                "description": "",
                "checkInDate": "",
                "checkOutDate": "",
            }
        )

        # --- Loop through bookings to add rooms ---
        for booking in hotel_bookings:
            hotel_offer = booking.get("hotelOffer", {})
            price_info = hotel_offer.get("price", {})
            room_info = hotel_offer.get("room", {})

            room_type = room_info.get("type", "ROOM")
            item_code = f"ROOM-{room_type}"
            description = room_info.get("description", {}).get("text", "Room Booking")
            qty = hotel_offer.get("roomQuantity", 1)
            rate = float(price_info.get("total", 0.0))

            room_groups[item_code]["qty"] += qty
            room_groups[item_code]["rate"] = rate  # Since total is for one room
            room_groups[item_code]["description"] = description
            room_groups[item_code]["checkInDate"] = hotel_offer.get("checkInDate", "")
            room_groups[item_code]["checkOutDate"] = hotel_offer.get("checkOutDate", "")

        # --- Ensure Items & Add to Invoice ---
        for item_code, data in room_groups.items():
            # Create item if it doesn't exist
            if not frappe.db.exists("Item", item_code):
                item = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": data["description"][:140],
                    "description": data["description"],
                    "stock_uom": "Nos",
                    "is_stock_item": 0,
                    "item_group": "Rooms",
                    "standard_rate": data["rate"],
                })
                item.insert(ignore_permissions=True)

            # Add to invoice
            invoice.append("items", {
                "item_code": item_code,
                "item_name": data["description"][:140],
                "description": f"{data['description']} | Check-in: {data['checkInDate']} | Check-out: {data['checkOutDate']}",
                "qty": data["qty"],
                "rate": data["rate"],
            })

        # --- Save and Submit ---
        invoice.insert(ignore_permissions=True)
        invoice.submit()

        add_payment_to_sales_invoice(
            invoice_name=invoice.name,
            paid_amount=invoice.grand_total,  # Assuming full payment
            payment_mode=payload.get(
                "payment_mode"
            ),  # Default payment mode, can be changed
            paid_date=invoice.posting_date,
        )

        return {
            "message": f"Sales Invoice {invoice.name} created successfully.",
            "invoice": invoice.name,
        }

    except Exception as e:
        print(f"Error creating sales invoice: {e}")
        frappe.log_error(frappe.get_traceback(), "Reservation Invoice Error")
        frappe.throw(f"Failed to create sales invoice: {e}")

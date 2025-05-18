import frappe
from frappe import _
from frappe.utils import getdate, add_days
from datetime import datetime, timedelta, date

def create_room_prices_on_submit(doc, method):
    if not doc.get('custom_is_hotel_purchase'):
        return
    
    for item in doc.items:        
        room = get_room_from_item(item.item_code)
        if not room:
            frappe.msgprint(_("Room not found for item {0}. Skipping Room Price creation.").format(item.item_code))
            continue
        
        start_date = getdate(item.custom_start_date)
        end_date = getdate(item.custom_end_date)        
        price_per_night = item.rate
        
        room_price  = create_room_price(
	        invoice_id=item.parent,
            room=room,
            start_date=start_date,
            end_date=end_date,
            price_per_night=price_per_night
        )
        create_room_availability(item , room_price)
    
    frappe.msgprint(_("Room Price records created successfully"))

def get_room_from_item(item_code):
    room = frappe.get_value("Room", {"item_id": item_code}, "name")
    return room

def create_room_price(invoice_id ,room, start_date, end_date, price_per_night):
    room_price = frappe.new_doc("Room Price")
    room_price.room_id = room  
    room_price.invoice_id = invoice_id  
    room_price.start_date = start_date
    room_price.end_date = end_date
    room_price.price_per_night = price_per_night
    room_price.insert()
    return room_price


def create_room_availability(item,room_price):
    room = frappe.get_doc('Room' , room_price.room_id)
    room_type = frappe.get_doc('Room Type' , room.room_type)
    hotel = frappe.get_doc('Hotel' , room.hotel)

    to_date = lambda d: d if isinstance(d, date) else datetime.strptime(str(d), "%Y-%m-%d").date()
    start = to_date(room_price.start_date)
    end   = to_date(room_price.end_date)
    print(hotel.name)
    current = start
    while current <= end:
        frappe.get_doc({
            "doctype":          "Room Availability",
            "room_id":          room.name,
            "date":             current,
            "hotel_id":         hotel.name,
            "available_rooms":  item.custom_room_quantity,
            "adults_per_room":  room_type.max_adults,
            "childs_per_room":  room_type.max_childs,
            "price":            room_price.price_per_night,
        }).insert()

        current += timedelta(days=1)

    frappe.db.commit() 
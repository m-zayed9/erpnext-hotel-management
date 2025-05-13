import frappe
from frappe import _
from frappe.utils import getdate
from collections import defaultdict

@frappe.whitelist(allow_guest=True)
def search(checkin_date, checkout_date, adults, childs, rooms):
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

    num_days = (checkout_date - checkin_date).days + 1
    hotel_rooms = defaultdict(list)

    for (room_id, hotel_id), entries in grouped.items():
        if len(entries) != num_days:
            continue

        min_avail = min(e.available_rooms for e in entries)
        avg_price = sum(float(e.price) for e in entries) / num_days

        if (entries[0].adults_per_room < int(adults) or
            entries[0].childs_per_room < int(childs) or
            min_avail < int(rooms)):
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
            "amenities": [a.amenity_id for a in hotel_doc.amenities]
        }

        lowest_avg_price = min(r["average_price"] for r in room_list)

        results.append({
            "hotel": hotel_data,
            "rooms": room_list,
            "lowest_avg_price": lowest_avg_price
        })

    return results


@frappe.whitelist(allow_guest=True)
def get_hotel_rooms(hotel_id, checkin_date, checkout_date, adults, childs, rooms):
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
        "amenities": [a.amenity_id for a in hotel_doc.amenities]
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
        
        if (entries[0].adults_per_room < int(adults) or
            entries[0].childs_per_room < int(childs) or
            min_avail < int(rooms)):
            continue
        
        # Get room details
        room_doc = frappe.get_doc("Room", room_id)
        
        # Get room type details
        room_type_doc = frappe.get_doc("Room Type", room_doc.room_type)
        
        # Prepare daily prices

        
        room_data = {
            "room_id": room_id,
            "available_rooms": min_avail,
            "average_price": round(avg_price, 2),
            "images": [img.image for img in room_doc.images],
            "amenities": [a.amenity_id for a in room_doc.amenities],
            "room_type": {
                "name": room_type_doc.room_type_name,
                "description": room_type_doc.description,
                "board_type": room_type_doc.board_type,
                "beds": room_type_doc.beds,
                "max_adults": room_type_doc.max_adults,
                "max_childs": room_type_doc.max_childs,
                'currency': get_default_currency()
            }
        }
        
        rooms_data.append(room_data)
    
    # Sort rooms by price (lowest first)
    rooms_data.sort(key=lambda x: x["average_price"])
    
    return {
        "hotel": hotel_data,
        "rooms": rooms_data
    }


@frappe.whitelist(allow_guest=True)
def get_room_details(room_id, checkin_date, checkout_date, adults, childs, rooms):
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
        "amenities": [a.amenity_id for a in hotel_doc.amenities]
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
        
        if (entries[0].adults_per_room < int(adults) or
            entries[0].childs_per_room < int(childs) or
            min_avail < int(rooms)):
            continue
        
        # Get room details
        room_doc = frappe.get_doc("Room", room_id)
        
        # Get room type details
        room_type_doc = frappe.get_doc("Room Type", room_doc.room_type)
        
        # Prepare daily prices

        
        room_data = {
            "room_id": room_id,
            "available_rooms": min_avail,
            "average_price": round(avg_price, 2),
            "images": [img.image for img in room_doc.images],
            "amenities": [a.amenity_id for a in room_doc.amenities],
            "room_type": {
                "name": room_type_doc.room_type_name,
                "description": room_type_doc.description,
                "board_type": room_type_doc.board_type,
                "beds": room_type_doc.beds,
                "max_adults": room_type_doc.max_adults,
                "max_childs": room_type_doc.max_childs,
                'currency': get_default_currency()
            }
        }
        
        rooms_data.append(room_data)
    
    return {
        "hotel": hotel_data,
        "room": rooms_data[0]
    }



def get_default_currency():
    global_defaults = frappe.get_doc("Global Defaults", "Global Defaults")
    currency = global_defaults.default_currency
    return currency